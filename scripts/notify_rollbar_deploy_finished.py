import requests
import subprocess
from django.conf import settings

environment = 'production'
# fetch last committed revision in the locally-checked out branch
git_process = subprocess.run(['git', 'log', '-n', '1', '--pretty=format:%H'], capture_output=True, check=True)
revision = git_process.stdout.decode()

response = requests.post('https://api.rollbar.com/api/1/deploy/', json={
    'environment': settings.ROLLBAR['environment'],
    'revision': revision
}, headers={
    'X-Rollbar-Access-Token': settings.ROLLBAR['access_token'],
}, timeout=3)

response.raise_for_status()
