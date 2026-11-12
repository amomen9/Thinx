# Handling the real interview data (D-S9)

The real coded interview data describes victims of trafficking, sexual violence
and torture, and includes minors. It was provided by Prof. van Reisen and its
analysis was approved by the teaching team. Rules for the group:

1. **One copy per person, on an encrypted device.** Keep it only in
   `~/Documents/DSIP-real-data/` on a laptop with FileVault, BitLocker or LUKS
   (check with `./scripts/check_encryption_at_rest.sh`). Delete the copies in
   Downloads and chat apps.
2. **Never in Git or shared drives.** `*.xlsx` and `real_data/` are in
   `.gitignore`; do not upload the file to Google Drive, WhatsApp or e-mail.
3. **Share only what is needed.** Reports, slides and chats contain the
   structure (column names, number of rows) and aggregated counts, never names,
   interviewee numbers, ages or other values of a single person.
4. **Delete after use.** When the project ends (after the final report), delete
   the folder and empty the Trash.

Verification: `./scripts/check_real_data.sh` checks that the disk is encrypted,
that no data file was ever committed, that `real_data/` is ignored and that no
copy of the file exists outside the allowed folder.
