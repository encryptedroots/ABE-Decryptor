# ABE-Decryptor

A Windows proof-of-concept for researching App-Bound Encryption (ABE) in Chromium-based browsers.

## Features & Compatibility

- Supports Chromium-based browsers including Google Chrome, Brave, and Microsoft Edge
- Tested against recent stable Chromium releases
- Windows x64 support
- Does not require administrator privileges for the demonstrated research workflow
- Python-based build system

## Overview

ABE-Decryptor demonstrates research into the App-Bound Encryption mechanisms used by Chromium-based browsers and the handling of data protected by those mechanisms.

The project is intended primarily as a proof of concept for studying Chromium's ABE implementation and related Windows components.

## Building

### Requirements

- Python 3.12 or another recent Python 3 version
- MSVC x64 build environment
- Visual Studio or the corresponding Build Tools

### Process

Open a command prompt with the x64 MSVC environment enabled and run:

```text
python builder.py
```

Build output is placed in the `build` directory.

Additional Python dependencies can be installed with:

```text
pip install -r requirements.txt
```

## Limitations

This project is a proof of concept and is not intended for production use.

### Platform Support

Currently supported:

- Windows x64

Windows ARM64 is not currently supported.

### Detection

The implementation does not include EDR or antivirus evasion techniques.

It relies on conventional Windows APIs and should therefore be expected to trigger security products. The project is intended for research and analysis rather than stealth or evasion.

## Third-Party Research

This project builds upon publicly available research into Chromium's App-Bound Encryption implementation.

Relevant research:

`xaitax/Chrome-App-Bound-Encryption-Decryption`

See `THIRD_PARTY_LICENSES` for information regarding third-party code and licensing.

## Disclaimer

ABE-Decryptor is provided for security research, reverse engineering, and educational purposes.

It is not intended to obtain unauthorized access to user data, bypass security controls, or be incorporated into malware or other malicious software.
