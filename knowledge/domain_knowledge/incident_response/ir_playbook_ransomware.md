# Incident Response Playbook: Ransomware Attack

**Document ID:** IR-001
**Author:** Sarah Chen
**Last Updated:** 2025-08-10

## 1. Triage & Identification

The first priority is to confirm the nature of the incident.

- **Initial Indicators:**
  - Users reporting inability to access files.
  - Ransom notes appearing on desktops or in directories.
  - Antivirus or EDR alerts for suspicious file encryption activity.
- **Action:** Immediately engage the Incident Response team.

## 2. Containment

The primary goal of containment is to prevent the ransomware from spreading further across the network.

- **Isolate Infected Systems:** Disconnect the affected machines from the network immediately. This includes disabling network interfaces (unplugging ethernet cables, turning off Wi-Fi).
- **Secure Backups:** Verify that backups are secure and isolated from the primary network. Do not attempt to restore from backups until all infected systems are identified and cleaned.
- **Change Credentials:** Reset all passwords for accounts that were active on the infected machines, especially administrative and service accounts.

## 3. Eradication & Recovery

Once contained, the threat must be removed and systems restored.

- **Identify the Ransomware Strain:** Use threat intelligence sources and ransom note details to identify the specific ransomware variant. This can help determine if a public decryptor is available.
- **Wipe and Rebuild:** The safest method for eradication is to wipe the affected systems completely and rebuild them from a known-good, clean image.
- **Restore from Backups:** After systems are rebuilt, restore data from the most recent, verified-clean backups.

## 4. Post-Incident Review

A thorough review is critical to prevent future incidents.

- **Root Cause Analysis:** Determine the initial infection vector (e.g., phishing email, unpatched vulnerability).
- **Lessons Learned:** Document the incident timeline, the effectiveness of the response, and any gaps in security controls.
- **Update Security Policies:** Implement new preventative measures based on the root cause analysis, such as enhanced email filtering, faster vulnerability patching, or improved user training.
