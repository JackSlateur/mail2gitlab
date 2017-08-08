#!/usr/bin/python3

from gitlab import Gitlab
import imaplib
import email
import email.header
import requests
import base64
import re
from collections import namedtuple

# Gitlab FQDN
gitlab = 'https://gitlab.fqdn'

# "Bot"'s token, it should be admin
# To fetch it: https://gitlab.fqdn/profile/account
token = 'N9LsUHXweDTs-TArTDhv'

# Created issues are tagged
label = 'mail2gitlab'

# Imap server to connect to
# Currently, all email addresses are retrieved on a single server
imap_server = 'imap.fqdn'

# If the sender matches the following regexp, we will create an issue, even if
# no gitlab account is found
# This is some kind of "antispam" stuff
trusted_from = '.*@fqdn'

Project = namedtuple('Project', ['mail', 'password', 'id'])
# What should we do ?
# Project id identifies the project inside gitlab
# Grab it here : https://gitlab.fqdn/bob/superproject/edit
conf = [
	Project('mail1@fqdn', 'pass1', 150),
	Project('mail2@fqdn', 'pass2', 42),
]


def get_first_text_block(mail):
	maintype = mail.get_content_maintype()
	if maintype == 'multipart':
		for part in mail.walk():
			if part.get_content_maintype() == 'text':
				return part.get_payload(decode=True)
	elif maintype == 'text':
		return mail.get_payload(decode=True)


def get_attachments(mail):
	if mail.get_content_maintype() != 'multipart':
		return list()

	result = list()
	for part in mail.walk():
		if part.get_filename() is not None:
			b64 = part.get('Content-Transfer-Encoding')
			if b64 is not None and b64 == 'base64':
				payload = base64.b64decode(part.get_payload())
			else:
				payload = part.get_payload()
			result.append({'filename': part.get_filename(), 'payload': payload})
	return result


def push_attachments(mail, body, proj_id):
	attachments = get_attachments(mail)
	for attachment in attachments:
		files = {
				'file': (attachment['filename'], attachment['payload'])
			}

		result = requests.post('%s/api/v4/projects/%s/uploads' % (gitlab, proj_id),
			headers={'PRIVATE-TOKEN': token},
			files=files)
		result.raise_for_status()
		body += """
%s
""" % (result.json()['markdown'],)
	return body


def sudo(git, mail):
	try:
		fake_uid = git.getusers(email.utils.parseaddr(mail['From']))[0]['id']
		git.setsudo(str(fake_uid))
		return True
	except IndexError:
		From = email.header.decode_header(mail['From'])[0][0]
		if re.match(trusted_from, From):
			# We found one of the team without a gitlab account: using default
			git.setsudo()
			return True

	# Nothing found, droping
	return False


def create_label(git, project_id):
	labels = git.getlabels(project_id)
	for i in labels:
		if i['name'] == label:
			return
	git.createlabel(project_id, label, '#D10069')


def work(login, password, project_id):
	git = Gitlab(gitlab, token=token)
	create_label(git, project_id)
	box = imaplib.IMAP4_SSL(imap_server)
	box.login(login, password)
	box.select('inbox')
	result, data = box.search(None, 'ALL')
	for _id in data[0].split():
		# Reset sudo before each run
		git.setsudo()

		result, data = box.fetch(_id, '(RFC822)')
		mail = email.message_from_string(data[0][1].decode('ascii', errors='ignore'))
		body = """```
%s
```""" % (get_first_text_block(mail).decode('utf-8'))

		if sudo(git, mail) is True:
			body = push_attachments(mail, body, project_id)
			subject = email.header.decode_header(mail['Subject'])[0][0]
			issue = git.createissue(project_id, title=subject, labels=label)
			git.createissuewallnote(project_id, issue['id'], body)

		box.store(_id, '+FLAGS', '\\Deleted')
	box.expunge()


if __name__ == '__main__':
	for i in conf:
		work(i.mail, i.password, i.id)
