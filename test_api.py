"""Integration tests against a REAL MySQL server (uses a separate database, challengehire_test).
Run from the project folder:  pytest -q   (needs DB_* in .env or the environment)"""
import os, sys
os.environ['DB_NAME'] = 'challengehire_test'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest, init_db, app as A

@pytest.fixture(scope='module')
def seeded():
    init_db.main(reset=True)

def client(): return A.app.test_client()
def login(c, email, pw='Password123!'): return c.post('/api/login', json=dict(email=email, password=pw))

def test_health_and_static(seeded):
    c = client(); assert c.get('/api/health').json['ok'] and b'ChallengeHire' in c.get('/').data

def test_register_validation_and_login(seeded):
    c = client()
    assert c.post('/api/register', json=dict(role='student', name='Z', email='bad', password='x')).status_code == 400
    r = c.post('/api/register', json=dict(role='student', name='New Student', email='new@test.dev', password='longenough1', college='X', skills='Python, SQL'))
    assert r.status_code == 201
    assert c.post('/api/register', json=dict(role='student', name='New Student', email='new@test.dev', password='longenough1')).status_code == 409
    me = c.get('/api/bootstrap').json; assert me['me'] and me['db']['users'][0]['skills'] == ['Python', 'SQL']
    assert login(client(), 'new@test.dev', 'wrong').status_code == 401

def test_role_protection(seeded):
    anon = client(); assert anon.post('/api/jobs/1/apply').status_code == 401
    st = client(); login(st, 'student@demo.dev')
    assert st.post('/api/jobs', json={}).status_code == 403
    assert st.post('/api/submissions/1/grade', json=dict(score=1)).status_code == 403

def test_apply_duplicate_submit_grade_flow(seeded):
    st = client(); login(st, 'student@demo.dev'); jobs = st.get('/api/bootstrap').json['db']['jobs']
    j3 = next(j for j in jobs if j['title'] == 'Data Analyst Trainee')
    assert st.post(f"/api/jobs/{j3['id']}/apply").status_code == 201
    assert st.post(f"/api/jobs/{j3['id']}/apply").status_code == 409
    assert st.post(f"/api/challenges/{j3['ch']}/submit", json=dict(link='not-a-url')).status_code == 400
    assert st.post(f"/api/challenges/{j3['ch']}/submit", json=dict(link='https://github.com/a/b', note='done')).status_code == 201
    d = st.get('/api/bootstrap').json['db']; app_ = next(a for a in d['apps'] if a['job'] == j3['id']); assert app_['status'] == 'Under Review'
    sub = next(s for s in d['subs'] if s['ch'] == j3['ch']); assert sub['score'] is None
    other = client(); login(other, 'recruiter@demo.dev')   # NovaTech recruiter does not own DataLeaf's challenge
    assert other.post(f"/api/submissions/{sub['id']}/grade", json=dict(score=50)).status_code == 404
    rec = client(); login(rec, 'karthik@demo.dev')
    assert rec.post(f"/api/submissions/{sub['id']}/grade", json=dict(score=101)).status_code == 400
    assert rec.post(f"/api/submissions/{sub['id']}/grade", json=dict(score=77, feedback='Good')).status_code == 200
    assert rec.post(f"/api/applications/{app_['id']}/status", json=dict(status='Shortlisted')).status_code == 200
    d = st.get('/api/bootstrap').json['db']
    assert next(s for s in d['subs'] if s['id'] == sub['id'])['score'] == 77 and next(a for a in d['apps'] if a['id'] == app_['id'])['status'] == 'Shortlisted'

def test_recruiter_posts_job_and_challenge(seeded):
    r = client(); login(r, 'recruiter@demo.dev')
    ch = r.post('/api/challenges', json=dict(title='Test Challenge', statement='Build a thing properly.', skills='Python', diff='Easy', max=10, criteria='Works', deadline='2099-01-01'))
    assert ch.status_code == 201
    j = r.post('/api/jobs', json=dict(title='Test Job', desc='A job description.', skills='Python, Git', level='Fresher', type='Contract', loc='Remote', deadline='2099-01-01', ch=str(ch.json['id'])))
    assert j.status_code == 201
    assert r.post('/api/jobs', json=dict(title='Past', desc='A job description.', skills='Python', level='x', type='Contract', loc='x', deadline='2001-01-01')).status_code == 400
    assert r.post(f"/api/jobs/{j.json['id']}/toggle").status_code == 200
    jobs = r.get('/api/bootstrap').json['db']['jobs']; assert next(x for x in jobs if x['id'] == str(j.json['id']))['open'] == 0

def test_database_down_gives_clear_error(seeded, monkeypatch):
    monkeypatch.setenv('DB_PORT', '1')
    r = client().get('/api/health'); assert r.status_code == 503 and 'Database unavailable' in r.json['error']
