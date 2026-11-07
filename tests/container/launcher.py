from unittest.mock import patch
from viewer_launcher import create_app
app = create_app()
with app.test_client() as client, patch('viewer_launcher.main.routes.docker.DockerClient') as docker:
    assert client.get('/').status_code == 200
    r = client.post('/cvlauncher', json={'cv_name':'layer','layer_type':'image','cv_path':'/fixture','session_name':'session','cv_container_name':'cv'})
    assert r.status_code == 200
    docker.return_value.containers.run.assert_called_with('cloudv_viewer:test',volumes={'/fixture':{'bind':'/mnt/data','mode':'ro'}},network='lightserv-test',name='cv',detach=True)
    r = client.post('/nglauncher',json={'ng_container_name':'ng','session_name':'session','hosturl':'localhost'})
    assert r.status_code == 200
    docker.return_value.containers.run.assert_called_with('nglancer_viewer:test',environment={'HOSTURL':'localhost','SESSION_NAME':'session','FLASK_MODE':'TEST'},network='lightserv-test',name='ng',detach=True)
print('PASS: launcher HTTP and existing Docker image/network/mount/environment contracts (Docker API mocked)')
