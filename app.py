"""ChallengeHire Flask API + static frontend, backed by MySQL."""
import os, re, secrets
from datetime import date, datetime
from functools import wraps
import pymysql, pymysql.cursors
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
load_dotenv()
STATUSES = ['Applied', 'Assessment Pending', 'Under Review', 'Shortlisted', 'Rejected', 'Selected']
app = Flask(__name__, static_folder='static', static_url_path='')
if not os.environ.get('SECRET_KEY'): print('WARNING: SECRET_KEY not set in .env; sessions reset on every restart.')
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32), SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_HTTPONLY=True, MAX_CONTENT_LENGTH=1 << 20)

class ApiError(Exception):
    def __init__(s, msg, code=400): s.msg, s.code = msg, code

def db():
    if 'db' not in g:
        g.db = pymysql.connect(host=os.environ.get('DB_HOST', 'localhost'), port=int(os.environ.get('DB_PORT', 3306)), user=os.environ.get('DB_USER', 'root'),
            password=os.environ.get('DB_PASSWORD', ''), database=os.environ.get('DB_NAME', 'challengehire'), charset='utf8mb4', connect_timeout=5, cursorclass=pymysql.cursors.DictCursor)
    return g.db
@app.teardown_appcontext
def _close(_):
    c = g.pop('db', None)
    if c: c.close()
@app.after_request
def _finish(r):  # commit only when the request succeeded
    if 'db' in g: (g.db.commit() if r.status_code < 400 else g.db.rollback())
    return r
def q(sql, a=()):
    with db().cursor() as c: c.execute(sql, a); return c.fetchall()
def q1(sql, a=()):
    r = q(sql, a); return r[0] if r else None
def x(sql, a=()):
    with db().cursor() as c: c.execute(sql, a); return c.lastrowid

@app.errorhandler(ApiError)
def _api(e): return jsonify(error=e.msg), e.code
@app.errorhandler(pymysql.err.OperationalError)
def _op(e):
    app.logger.error('Database unavailable: %s', e)
    return jsonify(error='Database unavailable. Check that MySQL is running and the DB_* settings in .env are correct.'), 503
@app.errorhandler(pymysql.MySQLError)
def _my(e):
    app.logger.exception(e); return jsonify(error='A database error occurred. Check the server log.'), 500
@app.errorhandler(HTTPException)
def _http(e): return jsonify(error=e.description), e.code
@app.errorhandler(Exception)
def _any(e):
    app.logger.exception(e); return jsonify(error='Unexpected server error.'), 500

# ---------- helpers ----------
def body():  # requires Content-Type: application/json, which also blocks cross-site form posts (CSRF)
    d = request.get_json(silent=True)
    if not isinstance(d, dict): raise ApiError('Send a JSON body.')
    return d
def txt(d, k, mn=1, mx=255, label=None):
    v = str(d.get(k) or '').strip()
    if not mn <= len(v) <= mx: raise ApiError(f'{label or k.capitalize()} must be {mn} to {mx} characters.')
    return v
def skills_in(v):
    items = v if isinstance(v, list) else str(v or '').split(',')
    out = {}
    for s in items:
        s = str(s).strip()
        if s:
            if len(s) > 50: raise ApiError('Each skill must be 50 characters or fewer.')
            out.setdefault(s.lower(), s)
    if len(out) > 30: raise ApiError('Use at most 30 skills.')
    return list(out.values())
def future(d, k, label):
    try: v = datetime.strptime(str(d.get(k)), '%Y-%m-%d').date()
    except ValueError: raise ApiError(f'{label} must be a valid date.')
    if v < date.today(): raise ApiError(f'{label} cannot be in the past.')
    return v
def set_skills(tbl, col, rid, names):
    x(f'DELETE FROM {tbl} WHERE {col}=%s', (rid,))
    for n in names:
        x('INSERT IGNORE INTO skills(name) VALUES(%s)', (n,))
        x(f'INSERT IGNORE INTO {tbl}({col},skill_id) SELECT %s,id FROM skills WHERE name=%s', (rid, n))
def need(role):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            uid = session.get('uid'); u = q1('SELECT * FROM users WHERE id=%s', (uid,)) if uid else None
            if not u: raise ApiError('Please log in first.', 401)
            if u['role'] != role: raise ApiError(f'Only {role}s can do this.', 403)
            g.u = u; return f(*a, **k)
        return w
    return deco
def smap(tbl, col):
    m = {}
    for r in q(f'SELECT t.{col} k, s.name FROM {tbl} t JOIN skills s ON s.id=t.skill_id ORDER BY s.name'): m.setdefault(str(r['k']), []).append(r['name'])
    return m
def inlist(ids): return ','.join(['%s'] * len(ids))

# ---------- serializers (ids are strings; shape matches what the frontend expects) ----------
def users_out(ids):
    if not ids: return []
    sm = smap('student_skills', 'user_id')
    return [dict(id=str(r['id']), role=r['role'], name=r['name'], college=r['college'] or '', skills=sm.get(str(r['id']), []), company=r['company'])
        for r in q(f'SELECT u.*,c.name company FROM users u LEFT JOIN companies c ON c.id=u.company_id WHERE u.id IN ({inlist(ids)})', list(ids))]
def jobs_out():
    sm = smap('job_skills', 'job_id')
    return [dict(id=str(r['id']), title=r['title'], company=r['company'], owner=str(r['recruiter_id']), skills=sm.get(str(r['id']), []), level=r['level'], type=r['type'],
        loc=r['location'], salary=r['salary'] or '', deadline=str(r['deadline']), ch=str(r['ch']) if r['ch'] else None, open=int(r['is_open']), desc=r['description'])
        for r in q('SELECT j.*,c.name company,(SELECT MIN(id) FROM challenges WHERE job_id=j.id) ch FROM jobs j JOIN companies c ON c.id=j.company_id ORDER BY j.id DESC')]
def challenges_out():
    sm = smap('challenge_skills', 'challenge_id')
    return [dict(id=str(r['id']), title=r['title'], owner=str(r['recruiter_id']), job=str(r['job_id']) if r['job_id'] else None, skills=sm.get(str(r['id']), []), diff=r['difficulty'],
        max=r['max_score'], deadline=str(r['deadline']), statement=r['statement'], criteria=r['criteria']) for r in q('SELECT * FROM challenges ORDER BY id DESC')]
def apps_out(where='1=1', a=()):
    return [dict(id=str(r['id']), job=str(r['job_id']), student=str(r['student_id']), status=r['status'], at=str(r['applied_at'])[:10])
        for r in q(f'SELECT a.* FROM applications a JOIN jobs j ON j.id=a.job_id WHERE {where} ORDER BY a.id', a)]
def subs_out(where='1=1', a=()):
    return [dict(id=str(r['id']), ch=str(r['challenge_id']), student=str(r['student_id']), link=r['link'], note=r['note'], score=r['score'], fb=r['feedback'] or '', at=str(r['submitted_at'])[:10])
        for r in q(f'SELECT s.*,e.score,e.feedback FROM submissions s JOIN challenges c ON c.id=s.challenge_id LEFT JOIN evaluation_results e ON e.submission_id=s.id WHERE {where} ORDER BY s.id', a)]

# ---------- routes ----------
@app.get('/')
def index(): return app.send_static_file('index.html')
@app.get('/api/health')
def health(): q1('SELECT 1'); return jsonify(ok=True)

@app.get('/api/bootstrap')
def bootstrap():
    uid = session.get('uid'); u = q1('SELECT * FROM users WHERE id=%s', (uid,)) if uid else None
    if uid and not u: session.clear()
    d = dict(users=[], apps=[], subs=[], jobs=jobs_out(), challenges=challenges_out(),
        stats=dict(students=q1("SELECT COUNT(*) n FROM users WHERE role='student'")['n'], submissions=q1('SELECT COUNT(*) n FROM submissions')['n']))
    if u and u['role'] == 'student':
        d['apps'] = apps_out('a.student_id=%s', (u['id'],)); d['subs'] = subs_out('s.student_id=%s', (u['id'],)); d['users'] = users_out([u['id']])
    elif u:
        d['apps'] = apps_out('j.recruiter_id=%s', (u['id'],)); d['subs'] = subs_out('c.recruiter_id=%s', (u['id'],))
        d['users'] = users_out({u['id']} | {int(r['student']) for r in d['apps']} | {int(r['student']) for r in d['subs']})
    return jsonify(me=str(u['id']) if u else None, db=d)

@app.post('/api/register')
def register():
    d = body(); role = d.get('role')
    if role not in ('student', 'recruiter'): raise ApiError('Choose a role: student or recruiter.')
    name = txt(d, 'name', 2, 100, 'Full name'); email = txt(d, 'email', 5, 190, 'Email').lower()
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email): raise ApiError('Enter a valid email address.')
    pw = str(d.get('password') or '')
    if len(pw) < 8: raise ApiError('Password must be at least 8 characters.')
    if q1('SELECT id FROM users WHERE email=%s', (email,)): raise ApiError('That email is already registered.', 409)
    cid = college = None; skills = []
    if role == 'recruiter':
        cname = txt(d, 'company', 2, 120, 'Company name')
        x('INSERT IGNORE INTO companies(name) VALUES(%s)', (cname,)); cid = q1('SELECT id FROM companies WHERE name=%s', (cname,))['id']
    else: college = str(d.get('college') or '').strip()[:150] or None; skills = skills_in(d.get('skills'))
    uid = x('INSERT INTO users(role,name,email,password_hash,college,company_id) VALUES(%s,%s,%s,%s,%s,%s)', (role, name, email, generate_password_hash(pw), college, cid))
    if role == 'student': set_skills('student_skills', 'user_id', uid, skills)
    session.clear(); session['uid'] = uid; return jsonify(ok=True), 201

@app.post('/api/login')
def login():
    d = body(); u = q1('SELECT * FROM users WHERE email=%s', (str(d.get('email') or '').strip().lower(),))
    if not u or not check_password_hash(u['password_hash'], str(d.get('password') or '')): raise ApiError('Incorrect email or password.', 401)
    session.clear(); session['uid'] = u['id']; return jsonify(ok=True)
@app.post('/api/logout')
def logout(): session.clear(); return jsonify(ok=True)

@app.post('/api/profile')
@need('student')
def profile():
    d = body(); x('UPDATE users SET college=%s WHERE id=%s', (str(d.get('college') or '').strip()[:150] or None, g.u['id']))
    set_skills('student_skills', 'user_id', g.u['id'], skills_in(d.get('skills'))); return jsonify(ok=True)

@app.post('/api/jobs')
@need('recruiter')
def post_job():
    d = body(); title = txt(d, 'title', 3, 150, 'Title'); desc = txt(d, 'desc', 10, 5000, 'Description'); skills = skills_in(d.get('skills'))
    if not skills: raise ApiError('Add at least one required skill.')
    if d.get('type') not in ('Full-time', 'Internship', 'Contract'): raise ApiError('Choose a valid job type.')
    dl = future(d, 'deadline', 'Deadline'); ch = d.get('ch') or None
    if ch and not q1('SELECT id FROM challenges WHERE id=%s AND recruiter_id=%s', (ch, g.u['id'])): raise ApiError('You can only link your own challenges.', 403)
    jid = x('INSERT INTO jobs(company_id,recruiter_id,title,description,level,type,location,salary,deadline) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
        (g.u['company_id'], g.u['id'], title, desc, txt(d, 'level', 1, 50, 'Level'), d['type'], txt(d, 'loc', 1, 100, 'Location'), str(d.get('salary') or '').strip()[:60] or None, dl))
    set_skills('job_skills', 'job_id', jid, skills)
    if ch: x('UPDATE challenges SET job_id=%s WHERE id=%s', (jid, ch))
    return jsonify(id=jid), 201

@app.post('/api/jobs/<int:jid>/toggle')
@need('recruiter')
def toggle_job(jid):
    if not x('UPDATE jobs SET is_open=1-is_open WHERE id=%s AND recruiter_id=%s', (jid, g.u['id'])) and not q1('SELECT id FROM jobs WHERE id=%s AND recruiter_id=%s', (jid, g.u['id'])):
        raise ApiError('Job not found or not yours.', 404)
    return jsonify(ok=True)

@app.post('/api/jobs/<int:jid>/apply')
@need('student')
def apply(jid):
    j = q1('SELECT j.*,(SELECT COUNT(*) FROM challenges WHERE job_id=j.id) n FROM jobs j WHERE id=%s', (jid,))
    if not j: raise ApiError('Job not found.', 404)
    if not j['is_open'] or j['deadline'] < date.today(): raise ApiError('This job is closed.')
    try: x('INSERT INTO applications(job_id,student_id,status) VALUES(%s,%s,%s)', (jid, g.u['id'], 'Assessment Pending' if j['n'] else 'Applied'))
    except pymysql.err.IntegrityError: raise ApiError('You already applied to this job.', 409)
    return jsonify(ok=True), 201

@app.post('/api/challenges')
@need('recruiter')
def post_challenge():
    d = body(); skills = skills_in(d.get('skills'))
    if not skills: raise ApiError('Add at least one skill.')
    if d.get('diff') not in ('Easy', 'Medium', 'Hard'): raise ApiError('Choose a valid difficulty.')
    try: mx = int(d.get('max') or 100)
    except ValueError: raise ApiError('Max score must be a whole number.')
    if not 1 <= mx <= 1000: raise ApiError('Max score must be between 1 and 1000.')
    jid = d.get('job') or None
    if jid and not q1('SELECT id FROM jobs WHERE id=%s AND recruiter_id=%s', (jid, g.u['id'])): raise ApiError('You can only link your own jobs.', 403)
    cid = x('INSERT INTO challenges(recruiter_id,job_id,title,statement,difficulty,max_score,criteria,deadline) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
        (g.u['id'], jid, txt(d, 'title', 3, 150, 'Title'), txt(d, 'statement', 10, 5000, 'Problem statement'), d['diff'], mx, txt(d, 'criteria', 3, 500, 'Evaluation criteria'), future(d, 'deadline', 'Deadline')))
    set_skills('challenge_skills', 'challenge_id', cid, skills); return jsonify(id=cid), 201

@app.post('/api/challenges/<int:cid>/submit')
@need('student')
def submit(cid):
    c = q1('SELECT * FROM challenges WHERE id=%s', (cid,)); d = body()
    if not c: raise ApiError('Challenge not found.', 404)
    if c['deadline'] < date.today(): raise ApiError('The submission deadline has passed.')
    link = txt(d, 'link', 8, 500, 'Link')
    if not re.match(r'https?://[^\s/]+\.[^\s/]+', link): raise ApiError('Enter a valid http(s) link.')
    x('INSERT INTO submissions(challenge_id,student_id,link,note) VALUES(%s,%s,%s,%s)', (cid, g.u['id'], link, str(d.get('note') or '').strip()[:500]))
    if c['job_id']: x("UPDATE applications SET status='Under Review' WHERE job_id=%s AND student_id=%s AND status='Assessment Pending'", (c['job_id'], g.u['id']))
    return jsonify(ok=True), 201

@app.post('/api/applications/<int:aid>/status')
@need('recruiter')
def set_status(aid):
    st = body().get('status')
    if st not in STATUSES: raise ApiError('Invalid status.')
    if not q1('SELECT a.id FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=%s AND j.recruiter_id=%s', (aid, g.u['id'])): raise ApiError('Application not found or not yours.', 404)
    x('UPDATE applications SET status=%s WHERE id=%s', (st, aid)); return jsonify(ok=True)

@app.post('/api/submissions/<int:sid>/grade')
@need('recruiter')
def grade(sid):
    d = body(); s = q1('SELECT c.max_score FROM submissions s JOIN challenges c ON c.id=s.challenge_id WHERE s.id=%s AND c.recruiter_id=%s', (sid, g.u['id']))
    if not s: raise ApiError('Submission not found or not yours.', 404)
    try: sc = int(d.get('score'))
    except (TypeError, ValueError): raise ApiError('Score must be a whole number.')
    if not 0 <= sc <= s['max_score']: raise ApiError(f"Score must be between 0 and {s['max_score']}.")
    x('INSERT INTO evaluation_results(submission_id,reviewer_id,score,feedback) VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE score=VALUES(score),feedback=VALUES(feedback),reviewer_id=VALUES(reviewer_id),evaluated_at=NOW()',
        (sid, g.u['id'], sc, str(d.get('feedback') or '').strip()[:1000]))
    return jsonify(ok=True)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)), debug=os.environ.get('FLASK_DEBUG') == '1')
