"""Seed historical ownership only; the retired event API must stay unavailable."""
import secrets,time

def archived_team(app, owner):
    team=secrets.token_hex(12)
    with app.db() as db:
        participant=db.execute('SELECT participant FROM agents WHERE id=?',(owner,)).fetchone()[0]
        db.execute("INSERT INTO agents(id,participant,created,kind) VALUES (?,?,?,'crew')",(team,participant,time.time()))
        db.execute('INSERT INTO crew_contexts VALUES (?,?,?)',(team,participant,'event-brief'))
        for role in range(9):
            row=dict(owner=team,role=role,native_id='bac-'+team+'-r'+str(role),workspace_name=team+'-'+str(role),chat_session='bac-crew-chat-'+team+'-'+str(role))
            db.execute('INSERT INTO crew_resources(owner,role,native_id,workspace_name,chat_session) VALUES (:owner,:role,:native_id,:workspace_name,:chat_session)',row)
            app.crew_resources[(team,role)]=row
    for role in (None,*range(9)):
        p=app.workspace(team,role);(p/'artifacts').mkdir(parents=True);(p/'inbox').mkdir()
    return team
