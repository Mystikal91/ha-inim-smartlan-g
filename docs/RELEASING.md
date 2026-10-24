# Publishing and releasing

Repository: https://github.com/Mystikal91/ha-inim-smartlan-g

## First publication
1. Create the public repository `ha-inim-smartlan-g` on GitHub (no README/licence, they already exist).
2. `git remote add origin https://github.com/Mystikal91/ha-inim-smartlan-g.git` then `git push -u origin main`.
3. In the repository settings add the description and the topics `home-assistant`, `hacs`,
   `hacs-integration`, `inim`, `alarm`, `smartlan`.
4. Check that the **Validate** workflow (hassfest, HACS, lint and tests) is green.

## Each release
1. Bump `version` in `custom_components/inim_smartlan/manifest.json`.
2. Commit, then tag with the same number: `git tag v0.1.0 && git push origin v0.1.0`.
3. On GitHub create a release from the tag (HACS uses the latest release to offer updates).

## Install with HACS (custom repository)
HACS -> menu -> Custom repositories -> URL above, type *Integration* -> Download -> restart Home Assistant.

## Default HACS list (optional)
Needs hassfest and the HACS action green, a release, and a pull request to `hacs/default`.
Check the current rules for brand images before submitting.
