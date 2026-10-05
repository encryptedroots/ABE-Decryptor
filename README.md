ABE-Decryption
tool that enables user-mode decryption of cookies for Chromium-based browsers that have implemented App-Bound Encryption (ABE)

Features & Compatibility
Works on Google Chrome, Brave and Microsoft Edge
Tested on the most recent stable version (Chromium v144)
Extracts all cookies from all profiles for each browser without requiring administrator privileges
Flow
For each of the three supported browsers, the script:

Checks the install path of the browser
Launches the browser in suspended mode
Sets up a named pipe using a deterministic algorithm for the name
Decodes the dll and writes it to a temp directory
Injects the dll into the browser using LoadLibraryA
Reads the encrypted ABE key from the browser's Local State file
Waits for the injected dll to connect to the pipe and sends the encrypted ABE key once connected
The dll calls the decrypt function on the browser's internal Elevator COM interface and sends the now decrypted ABE key back through the same pipe
Once the decrypted key is received, terminates the suspended process and closes the pipe
Finds all browser profiles and their associated cookie databases
Copies each cookie database to a temp directory, which might require killing the browser process if running
Extracts the cookies and decrypts them using the decrypted ABE key
Writes the decrypted cookies to cookies/{BROWSER NAME}_{PROFILE NAME}_cookies.txt in Netscape format
For a more detailed explanation of how the key decryption itself works, check out the Research done by xaitax

Building
Requirements
Python 3.12 (other recent Python 3 versions will likely work)
MSVC x64 build environment (e.g., “x64 Native Tools Command Prompt for VS”)
Process
Open a command prompt with a 64-bit MSVC environment enabled
Run python builder.py
The output file will be in build/injector.py
Optional
Install the requirements from requirements.txt via pip install -r requirements.txt

While this is not required for building the final file, it is a requirement to run the injector

Limitations
While this tool gets the job done, it is merely a POC and not meant to be used in a production environment, as it has several limitations

Platform Support
This tool only works on Windows x64
Windows ARM64 is currently not supported
Detection
This tool doesn't implement any EDR or AV evasion techniques and will therefore likely get detected by them
No Encryption: The dll is stored unencrypted as a base64 blob
No Syscalls: The entire process uses high-level Windows API calls, making it trivial for AV solutions to block them. This includes writing the dll to disk directly and using LoadLibraryA for injection
As chromium browsers can be very strict with who is allowed to access the cookie database, this also kills the browser process, making it very obvious to the user what is happening
Third-party Research
This project wouldn't have been possible without the research found in xaitax/Chrome-App-Bound-Encryption-Decryption. A good chunk of the C++ code of this project is also an adapted version of that project's chrome_decrypt.cpp. Check out THIRD_PARTY_LICENSES for information on the licensing.

Disclaimer
This is a proof-of-concept project and is NOT meant to be used to get unauthorized access to user data or to be used in malware campaigns
