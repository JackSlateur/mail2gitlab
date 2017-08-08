mail2gitlab
===

What is mail2gitlab
---

Mail2gitlab is a simple proxy between one/many IMAP account and one/many gitlab projects

For each new email, it will create an issue

If gitlab knows the From:, that user will be impersonated (effectively hidding the whole process)
If not, the generic user will create the issues (regexp-based filtering is possible there)

All email attachments will be linked to the issue


Requirements
---

```
aptitude install python3 python3-gitlab python3-requests
```

How to use
---

Simply run the script, hopefully via cron:
```
*/1 * * * * bob /usr/local/bin/mail2gitlab.py
```

