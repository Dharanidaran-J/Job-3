"""Create the database/tables from schema.sql and load clearly-labelled DEMO data.
Usage: python init_db.py            (create if missing, seed only when empty)
       python init_db.py --reset    (DROP the database first, then recreate)"""
import os, re, sys
from datetime import date, timedelta
import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
load_dotenv()
DEV_PASSWORD = 'Password123!'   # development-only password for all sample accounts
HERE = os.path.dirname(os.path.abspath(__file__))
day = lambda n: date.today() + timedelta(days=n)

def connect():
    return pymysql.connect(host=os.environ.get('DB_HOST', 'localhost'), port=int(os.environ.get('DB_PORT', 3306)),
        user=os.environ.get('DB_USER', 'root'), password=os.environ.get('DB_PASSWORD', ''), charset='utf8mb4', autocommit=False)

def main(reset=False):
    name = os.environ.get('DB_NAME', 'challengehire')
    if not re.fullmatch(r'\w+', name): raise SystemExit('DB_NAME may contain only letters, digits and underscores.')
    con = connect(); cur = con.cursor()
    if reset: cur.execute(f'DROP DATABASE IF EXISTS `{name}`')
    cur.execute(f'CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4'); cur.execute(f'USE `{name}`')
    sql = '\n'.join(l for l in open(os.path.join(HERE, 'schema.sql')).read().splitlines() if not l.startswith('--'))
    for st in sql.split(';'):
        if st.strip() and not re.match(r'\s*(CREATE DATABASE|USE)\b', st, re.I): cur.execute(st)
    cur.execute('SELECT COUNT(*) FROM users')
    if cur.fetchone()[0]: con.commit(); print('Schema ready; users exist, so demo data was not loaded.'); return
    def sk(n):
        cur.execute('INSERT IGNORE INTO skills(name) VALUES(%s)', (n,)); cur.execute('SELECT id FROM skills WHERE name=%s', (n,)); return cur.fetchone()[0]
    def link(tbl, col, rid, names):
        for n in names: cur.execute(f'INSERT INTO {tbl}({col},skill_id) VALUES(%s,%s)', (rid, sk(n)))
    pw = generate_password_hash(DEV_PASSWORD); co = {}
    for n in ('NovaTech (demo)', 'DataLeaf (demo)'):
        cur.execute('INSERT INTO companies(name) VALUES(%s)', (n,)); co[n] = cur.lastrowid
    def user(role, name, email, college=None, company=None, skills=()):
        cur.execute('INSERT INTO users(role,name,email,password_hash,college,company_id) VALUES(%s,%s,%s,%s,%s,%s)', (role, name, email, pw, college, co.get(company)))
        uid = cur.lastrowid; link('student_skills', 'user_id', uid, skills); return uid
    s1 = user('student', 'Aarav Menon', 'student@demo.dev', 'Anna University', skills=['HTML', 'CSS', 'JavaScript', 'Python'])
    s2 = user('student', 'Diya Raman', 'diya@demo.dev', 'PSG Tech', skills=['Python', 'SQL', 'Flask', 'Git'])
    r1 = user('recruiter', 'Priya Nair', 'recruiter@demo.dev', company='NovaTech (demo)')
    r2 = user('recruiter', 'Karthik S', 'karthik@demo.dev', company='DataLeaf (demo)')
    N, D = 'NovaTech (demo)', 'DataLeaf (demo)'
    jobs = [(N, r1, 'Frontend Developer Intern', 'Build responsive UI for our hiring tools with a small product team.', 'Fresher', 'Internship', 'Remote', 'Rs 15k-25k/mo', 20, ['HTML', 'CSS', 'JavaScript', 'React']),
      (N, r1, 'Backend Python Developer', 'Design REST APIs and MySQL schemas for recruitment workflows.', '0-2 years', 'Full-time', 'Chennai', 'Rs 5-8 LPA', 30, ['Python', 'Flask', 'SQL', 'Git']),
      (D, r2, 'Data Analyst Trainee', 'Turn raw data into dashboards and insights for retail clients.', 'Fresher', 'Full-time', 'Bengaluru', 'Rs 4-6 LPA', 25, ['SQL', 'Python', 'Excel', 'Statistics']),
      (D, r2, 'Full Stack Developer', 'Own features end to end across our analytics web app.', '1-3 years', 'Full-time', 'Hybrid, Pune', 'Rs 8-12 LPA', 15, ['JavaScript', 'Node.js', 'SQL', 'HTML', 'CSS']),
      (N, r1, 'QA Automation Engineer', 'Write automated test suites for web applications.', '0-2 years', 'Contract', 'Remote', None, 12, ['Python', 'Selenium', 'Git'])]
    j = []
    for c, r, t, d, lv, ty, loc, sal, dd, sks in jobs:
        cur.execute('INSERT INTO jobs(company_id,recruiter_id,title,description,level,type,location,salary,deadline) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)', (co[c], r, t, d, lv, ty, loc, sal, day(dd)))
        j.append(cur.lastrowid); link('job_skills', 'job_id', j[-1], sks)
    chs = [(r1, 0, 'Responsive Portfolio Page', 'Build a responsive personal portfolio page with a project gallery and a working contact form validation.', 'Easy', 100, 'Responsiveness 40, Code quality 30, Accessibility 30', 14, ['HTML', 'CSS', 'JavaScript']),
      (r1, 1, 'REST API for a Library System', 'Build a Flask API with CRUD for books and members, borrowing rules, and a MySQL schema with foreign keys.', 'Medium', 100, 'Schema design 35, API correctness 40, Docs 25', 21, ['Python', 'Flask', 'SQL']),
      (r2, 2, 'Sales Insights Notebook', 'Analyse the provided sales dataset and report three actionable insights with queries and charts.', 'Medium', 100, 'Query accuracy 40, Insight quality 40, Clarity 20', 18, ['SQL', 'Python', 'Statistics']),
      (r2, 3, 'College Attendance Manager', 'Build a simple college attendance management website using HTML, CSS, JavaScript, and a database.', 'Hard', 100, 'Functionality 40, Database design 30, UI 30', 24, ['HTML', 'CSS', 'JavaScript', 'SQL']),
      (r1, 4, 'Login Flow Test Suite', 'Write automated tests covering valid login, invalid login and lockout behaviour for a sample page.', 'Easy', 50, 'Coverage 50, Readability 30, Reporting 20', 10, ['Python', 'Selenium', 'Git'])]
    c = []
    for r, ji, t, st, df, mx, cr, dd, sks in chs:
        cur.execute('INSERT INTO challenges(recruiter_id,job_id,title,statement,difficulty,max_score,criteria,deadline) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)', (r, j[ji], t, st, df, mx, cr, day(dd)))
        c.append(cur.lastrowid); link('challenge_skills', 'challenge_id', c[-1], sks)
    cur.execute("INSERT INTO applications(job_id,student_id,status) VALUES(%s,%s,'Under Review'),(%s,%s,'Assessment Pending')", (j[1], s2, j[0], s1))
    cur.execute("INSERT INTO submissions(challenge_id,student_id,link,note) VALUES(%s,%s,'https://github.com/example/library-api','Flask + MySQL with session auth.')", (c[1], s2))
    cur.execute("INSERT INTO evaluation_results(submission_id,reviewer_id,score,feedback) VALUES(%s,%s,82,'Clean schema and good validation. Add pagination and tests.')", (cur.lastrowid, r1))
    con.commit(); print('Database ready. Demo data loaded (sample password for every demo account: %s).' % DEV_PASSWORD)

if __name__ == '__main__':
    try: main('--reset' in sys.argv)
    except pymysql.MySQLError as e: raise SystemExit(f'MySQL error: {e}\nCheck that MySQL is running and the DB_* values in .env are correct.')
