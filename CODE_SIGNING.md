# Code signing policy

Status: signing preparation only. This project has NOT been accepted by SignPath Foundation, has no production signing certificate, and currently distributes only explicitly labelled unsigned previews. The unsigned EXE is blocked by application control on the development PC. No signed release is claimed.

## Proposed provider

We intend to apply to SignPath Foundation's free program for open-source software. Acceptance requires its project verification and is not guaranteed. If accepted, the provider attribution required by the program would be: “Free code signing provided by SignPath.io, certificate by SignPath Foundation”. This is a proposed future attribution, not a claim that signing is currently provided.

References: https://signpath.org/terms and https://docs.signpath.io/trusted-build-systems/github

## Roles and release approval

Repository owner: https://github.com/killerwhale61con-lgtm

The proposed committer/reviewer and signing approver is the repository owner. The owner must confirm these responsibilities and enable multi-factor authentication on GitHub and SignPath before the signing program can be used. No approval authority is delegated to an automated workflow or AI agent. Changes from external contributors require maintainer review, including changes to build workflows and scripts. Every production signing request requires the owner's explicit approval in the signing service.

## Build and signing controls

Builds run on GitHub-hosted Windows runners from the public repository. Third-party Actions are pinned to reviewed commit IDs. The workflow has read-only repository contents permission and does not use production signing credentials. Artifact origin (repository, commit, workflow run) is recorded. EXE product name is CMYK Screen Separator, and product/file version is 0.3.0.0.

Only this project's own executable may be signed. GIMP or any other upstream executable is not bundled or signed under this project's identity. Worker scripts, source and GPL notices remain in the distribution. SignPath artifact restrictions and source-origin validation must be configured with the provider after acceptance. Production packages must be rebuilt from the reviewed source; the existing unsigned release is not silently replaced.

After signing, validate the executable's Authenticode trust and timestamp, package the signed executable, regenerate SHA-256 checksums and corresponding source, download the public artifact to Windows 11, and verify launch with the current application-control policy. Then verify the native UI, GIMP integration and the four JPEG outputs before calling it a usable signed release. A successful signature check alone is not a functional test.

## Privacy and uninstall

See [Privacy policy](PRIVACY.md). The program does not upload photographs or usage data to the developer. GIMP is separately installed third-party software. This portable application does not install a service or modify system configuration. Exit the app and delete its extracted directory to remove it. Local pending jobs/logs may remain under the user's LocalApplicationData/CMYKScreenSeparator directory; export wanted plates before removing that directory.
