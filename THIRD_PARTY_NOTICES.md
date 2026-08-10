# Third-Party Notices

File Organizer includes or uses the following third-party components. Their licenses remain separate from this project's MIT license.

## Python dependencies

The exact supported dependency ranges are listed in `requirements.txt`.

- FastAPI: MIT License. <https://github.com/fastapi/fastapi/blob/master/LICENSE>
- Uvicorn: BSD 3-Clause License. <https://github.com/encode/uvicorn/blob/master/LICENSE.md>
- Pydantic: MIT License. <https://github.com/pydantic/pydantic/blob/main/LICENSE>
- Pillow: HPND License. <https://github.com/python-pillow/Pillow/blob/main/LICENSE.md>
- pywebview: BSD 3-Clause License. <https://github.com/r0x0r/pywebview/blob/master/LICENSE>
- PyInstaller: GPLv2-or-later with the PyInstaller exception for distributing applications. <https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt>

PyInstaller is a build-time dependency. The optional AI SDKs are not required by the core application and are not bundled by the standard spec.

The macOS desktop build also bundles the runtime dependencies that `pywebview`
installs automatically on macOS:

- PyObjC core and frameworks (Cocoa, Quartz, Security, UniformTypeIdentifiers, WebKit): MIT License. <https://pypi.org/project/pyobjc/>
- bottle: MIT License. <https://bottlepy.org/docs/stable/>
- proxy_tools: MIT License. <https://pypi.org/project/proxy_tools/>
- typing_extensions: Python Software Foundation License. <https://pypi.org/project/typing-extensions/>

## Font Awesome

The local web assets under `static/vendor/fontawesome/` are Font Awesome Free 6.4.0:

- Icons: CC BY 4.0
- Fonts: SIL Open Font License 1.1
- CSS/code: MIT License

Official notice: <https://fontawesome.com/license/free>
