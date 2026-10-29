# Bugs

Fixed bugs and known issues for Digestion Lab, newest version first.
Every release updates this file along with the README changelog.

## Known issues

| # | Issue | Workaround / status |
|---|---|---|
| K1 | The Linux binary needs glibc 2.36 or newer (Debian 12, Ubuntu 23.04+). It won't start on older distros. | Build on the oldest distro you want to support. |
| K2 | Japanese text on Linux needs an installed CJK font; without one, Japanese characters don't display. | `sudo apt install fonts-noto-cjk` (the .deb recommends it). Windows already has fonts. |
| K3 | On Windows, `DigestionLab-v*.exe --version` prints nothing, because the game has no console window. | Check **Properties → Details** or the title screen. |
| K4 | The recorded burps and farts were chosen and checked by spectrogram, not yet by ear on real speakers. | Please report any clip that sounds wrong; it's easy to swap in a different CC0 recording. |
| K5 | The .exe has been tested under Wine, not yet on a real Windows PC. | Please report any Windows-only problem. |

## Fixed

### v0.1.2
| # | Bug | Fix |
|---|---|---|
| F9 | Burps and farts still sounded electronic, even with the physical-model synthesis. | Replaced with real recordings (CC0, Freesound), one per food, bundled in the binaries. |

### v0.1.1
| # | Bug | Fix |
|---|---|---|
| F6 | Burp and fart sounds were unrealistic: steady buzzy tones that sounded "stupid". | Rebuilt as physical models: irregular air puffs, throat/mouth formants for burps, body resonances, breath and wet crackle for farts. |
| F7 | Every burp and fart came out as a low hum, because the resonator filter's gain grew at low frequencies and drowned out the mouth/body shaping. | Replaced with constant-peak band-pass filters. |
| F8 | Building a new .exe deleted the previous version's .exe. | Old builds are kept in `dist/windows/`. |

### v0.1.0
| # | Bug | Fix |
|---|---|---|
| F1 | Japanese mode showed digits and Latin letters as empty boxes when the system's Japanese font had no Latin glyphs. | Text is rendered in runs: Japanese characters in the Japanese font, everything else in the Latin font. |
| F2 | The prediction button you picked was dimmed along with the others after answering. | The picked button keeps full color. |
| F3 | Title, settings and results cards had large empty gaps. | Card heights tightened. |
| F4 | The Windows build failed under Wine: the Python installer refused to run on Wine's default Windows 7 mode. | The build script sets the Wine prefix to Windows 10 and runs it on a virtual display. |
| F5 | Burp and fart sounds were the same for every food. | Each burp and fart food got its own sound. |
