# TOOLS.md - Local Notes

Skills define *how* tools work. This file is for *your* specifics — the stuff that's unique to your setup.

## Toggl Time Tracking

- **API Token:** 678e42a03e7c32b55be26d386f24e52e
- **Workspace ID:** 21034707
- **API Base:** https://api.track.toggl.com/api/v9

## What Goes Here

Things like:
- Camera names and locations
- SSH hosts and aliases  
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## SSH Servers

| Alias | Host | User | Purpose |
|-------|------|------|---------|
| `66.94.97.240` | 66.94.97.240 | jfielder | Unknown |
| `Hostinger` | 76.13.28.149 | redleif | Hosting |
| `CPS-VPS` | 154.38.181.239 | cps | CoParenting System |
| `Redleif-dev` | 194.140.199.114 | jodfie | Main homelab VPS |
| `GaScanner-Chatham-RIoT` | proxy8.remoteiot.com:30298 | trunk | Scanner - Chatham |
| `GaScanner-Cloud-Adminlocal` | 209.145.49.25 | adminlocal | Scanner cloud |
| `GaScanner-Cloud-Root` | 209.145.49.25 | root | Scanner cloud (root) |

**Note:** Need Jody to add this VPS's public key to each server's `authorized_keys` for access.

## Examples

```markdown
### Cameras
- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### TTS
- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.