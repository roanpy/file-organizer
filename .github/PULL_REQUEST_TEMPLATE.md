## Summary

- What user-visible behavior or maintenance change does this PR make?
- Why is the change needed?

## Safety and scope

- [ ] No API keys, tokens, private paths, logs, databases, models, caches, or downloaded files are included.
- [ ] Destructive file operations retain configured-root and confirmation safeguards.
- [ ] AI remains optional; local rules still work when AI is unavailable.

## Verification

- [ ] `python -m unittest discover -s tests -v`
- [ ] `python -m compileall -q src SoftwareOrganizer-Skill tests`
- [ ] `node --check static/app.js`
- [ ] `node --check static/i18n.js`
- [ ] `python scripts/check_public_safety.py`
- [ ] `python -m pip check`

## Documentation

- [ ] Relevant README, changelog, maintenance record, or third-party notice is updated.
- [ ] Screenshots and examples use synthetic data only.
