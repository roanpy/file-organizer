# -*- coding: utf-8 -*-
"""
AI Engine Module - Handles AI model calls and software analysis.
Optimized version: Supports native SDK fallback and automatic retries.
"""

import json
import importlib
import os
import re
import warnings
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",
]

DEFAULT_DEEPSEEK_MODELS = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-chat",
    "deepseek-reasoner",
]

# Retry Library
try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
    )
except ImportError:
    # Basic mock in case tenacity is missing
    def retry(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def stop_after_attempt(x):
        return None

    def wait_exponential(**kwargs):
        return None

    def retry_if_exception_type(x):
        return None


def _get_litellm():
    """Import LiteLLM only when a custom provider actually needs it."""
    module_name = "".join(["lite", "llm"])
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ImportError("LiteLLM not installed") from exc

    module.suppress_debug_info = True
    return module


def _get_gemini_sdk():
    """Import the deprecated Gemini SDK lazily and suppress its warning."""
    module_name = ".".join(["google", "generativeai"])
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            return importlib.import_module(module_name)
    except ImportError as exc:
        raise ImportError("Google Generative AI SDK not installed") from exc


def _get_openai_client_class():
    module_name = "".join(["open", "ai"])
    try:
        return getattr(importlib.import_module(module_name), "OpenAI")
    except ImportError as exc:
        raise ImportError("OpenAI SDK not installed") from exc


def _get_engine_config(config: Dict[str, Any], engine_choice: str) -> Optional[Dict]:
    """
    Get the configuration for a specific engine.
    """
    # 1. Check root level first
    if engine_choice in config and isinstance(config[engine_choice], dict):
        return config[engine_choice]

    # 2. Check built-in list (for legacy config)
    builtin_engines = ["gemini", "deepseek", "ollama"]
    if engine_choice in builtin_engines:
        val = config.get(engine_choice)
        if isinstance(val, dict):
            return val

    # 3. Check custom_providers
    custom_providers = config.get("custom_providers", {})
    return custom_providers.get(engine_choice)


def _parse_json_response(text: str) -> Any:
    """Clean and parse JSON from AI response."""
    cleaned = text.strip()
    # Remove markdown code blocks
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    return json.loads(cleaned.strip())


def _http_json_request(
    url: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
    method: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a JSON HTTP request using only the Python standard library."""
    data = None
    request_method = method or ("POST" if payload is not None else "GET")
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", **headers}

    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=request_method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict):
                error = parsed.get("error", parsed)
                if isinstance(error, dict):
                    message = error.get("message") or error.get("code")
                    if message:
                        detail = str(message)
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"网络连接失败: {exc.reason}") from exc

    if not body:
        return {}
    return json.loads(body)


def _normalize_gemini_model(model_name: Optional[str]) -> str:
    """Map empty or retired Gemini names to a current default model."""
    model = (model_name or "").strip()
    if model.startswith("models/"):
        model = model.split("/", 1)[1]
    if model.startswith("gemini/"):
        model = model.split("/", 1)[1]

    retired_or_empty = {
        "",
        "gemini-pro",
        "gemini-1.0-pro",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    }
    if model in retired_or_empty:
        return DEFAULT_GEMINI_MODELS[0]
    return model


def _normalize_deepseek_model(model_name: Optional[str]) -> str:
    """Map empty or retired DeepSeek names to the current fast default."""
    model = (model_name or "").strip()
    if model.startswith("deepseek/"):
        model = model.split("/", 1)[1]
    if model in {"", "deepseek-coder"}:
        return DEFAULT_DEEPSEEK_MODELS[0]
    return model


def _extract_gemini_text(response: Dict[str, Any]) -> str:
    candidates = response.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini 未返回候选结果")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [part.get("text", "") for part in parts if part.get("text")]
    content = "".join(text_parts).strip()
    if not content:
        raise RuntimeError("Gemini 返回内容为空")
    return content


def _call_gemini_http(
    engine_config: Dict[str, Any], prompt: str, json_mode: bool = True
) -> Any:
    api_key = engine_config.get("api_key")
    if not api_key:
        raise RuntimeError("Gemini API Key 未配置")

    model = _normalize_gemini_model(engine_config.get("model_name"))
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    generation_config: Dict[str, Any] = {
        "temperature": 0.2,
    }
    if json_mode:
        generation_config["responseMimeType"] = "application/json"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }
    data = _http_json_request(
        url,
        headers={"x-goog-api-key": api_key},
        payload=payload,
        timeout=90,
    )
    content = _extract_gemini_text(data)
    if json_mode:
        return _parse_json_response(content)
    return content


def _call_deepseek_http(
    engine_config: Dict[str, Any], prompt: str, json_mode: bool = True
) -> Any:
    api_key = engine_config.get("api_key")
    if not api_key:
        raise RuntimeError("DeepSeek API Key 未配置")

    model = _normalize_deepseek_model(engine_config.get("model_name"))
    base_url = (
        engine_config.get("url")
        or engine_config.get("base_url")
        or "https://api.deepseek.com"
    ).rstrip("/")
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.2,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    data = _http_json_request(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        payload=payload,
        timeout=90,
    )
    content = data["choices"][0]["message"].get("content", "")
    if json_mode:
        return _parse_json_response(content)
    return content


def _call_ollama_http(
    engine_config: Dict[str, Any], prompt: str, json_mode: bool = True
) -> Any:
    """Call Ollama through its local HTTP API; no Python SDK required."""
    model = (engine_config.get("model_name") or "").strip()
    if not model:
        raise RuntimeError("Ollama 模型未配置")

    base_url = (engine_config.get("url") or "http://127.0.0.1:11434").rstrip("/")
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    data = _http_json_request(
        f"{base_url}/api/chat",
        headers={},
        payload=payload,
        timeout=120,
    )
    content = data.get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("Ollama 返回内容为空")
    if json_mode:
        return _parse_json_response(content)
    return content


def list_gemini_models(api_key: str, limit: int = 20) -> List[str]:
    """Return Gemini text generation models visible to the API key."""
    if not api_key:
        return []

    data = _http_json_request(
        "https://generativelanguage.googleapis.com/v1beta/models",
        headers={"x-goog-api-key": api_key},
        method="GET",
        timeout=20,
    )
    models = []
    for item in data.get("models", []):
        methods = item.get("supportedGenerationMethods") or item.get(
            "supported_generation_methods", []
        )
        if "generateContent" not in methods:
            continue
        name = item.get("name", "")
        if name.startswith("models/"):
            name = name.split("/", 1)[1]
        if name:
            models.append(name)

    preferred = [model for model in DEFAULT_GEMINI_MODELS if model in models]
    remaining = [model for model in models if model not in preferred]
    return (preferred + remaining)[:limit]


def test_gemini_connection(api_key: str, model_name: str = "") -> List[str]:
    """Validate Gemini credentials and return candidate models."""
    models = list_gemini_models(api_key)
    selected = _normalize_gemini_model(model_name or (models[0] if models else ""))
    _call_gemini_http(
        {"api_key": api_key, "model_name": selected},
        'Return {"ok": true} as JSON.',
        json_mode=True,
    )
    return models or DEFAULT_GEMINI_MODELS


def test_deepseek_connection(
    api_key: str, model_name: str = "", base_url: str = ""
) -> List[str]:
    """Validate DeepSeek credentials and return supported model names."""
    model = _normalize_deepseek_model(model_name)
    _call_deepseek_http(
        {"api_key": api_key, "model_name": model, "base_url": base_url},
        'Return {"ok": true} as JSON.',
        json_mode=True,
    )
    return DEFAULT_DEEPSEEK_MODELS


# Define retry strategy: exponential backoff, up to 5 attempts, wait between 1~10 seconds.
# Specifically for LiteLLM RateLimitError or other temporary errors.
def _is_retryable_error(exception):
    """Determine if an exception is worth retrying."""
    # LiteLLM errors usually include APIError, RateLimitError etc.
    error_str = str(exception).lower()
    return (
        "ratelimit" in error_str
        or "quota" in error_str
        or "429" in error_str
        or "503" in error_str
        or "timeout" in error_str
    )


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _call_via_litellm(
    engine_choice: str,
    engine_config: Dict[str, Any],
    prompt: str,
    json_mode: bool = True,
) -> Any:
    """Call AI via LiteLLM with advanced retry logic."""
    litellm = _get_litellm()
    model_name = engine_config.get("model_name", "")
    api_key = engine_config.get("api_key")
    base_url = engine_config.get("url") or engine_config.get("base_url")

    # Construct model name
    if engine_choice == "gemini":
        # liteLLM format: gemini/gemini-pro
        if not model_name.startswith("gemini/"):
            full_model = f"gemini/{model_name}"
        else:
            full_model = model_name
    elif engine_choice == "deepseek":
        full_model = (
            f"deepseek/{model_name}"
            if not model_name.startswith("deepseek/")
            else model_name
        )
        if not base_url:
            base_url = "https://api.deepseek.com"
    elif engine_choice == "ollama":
        full_model = (
            f"ollama/{model_name}"
            if not model_name.startswith("ollama/")
            else model_name
        )
        if not base_url:
            base_url = "http://127.0.0.1:11434"
    else:
        # Custom
        full_model = model_name

    messages = [{"role": "user", "content": prompt}]

    kwargs = {
        "model": full_model,
        "messages": messages,
        # Disable internal litellm retries to give control to tenacity
        "num_retries": 0,
    }

    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["api_base"] = base_url

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content

    if json_mode:
        return _parse_json_response(content)
    return content


def _call_via_native_sdk(
    engine_choice: str,
    engine_config: Dict[str, Any],
    prompt: str,
    json_mode: bool = True,
) -> Any:
    """Native SDK call implementation."""
    content = ""

    if engine_choice == "gemini":
        genai = _get_gemini_sdk()

        genai.configure(api_key=engine_config.get("api_key"))
        # Gemini model_name does not need 'gemini/' prefix in native SDK
        mn = engine_config.get("model_name", "gemini-pro")
        if mn.startswith("gemini/"):
            mn = mn.replace("gemini/", "")

        model = genai.GenerativeModel(mn)
        response = model.generate_content(prompt)
        content = response.text

    elif engine_choice == "deepseek":
        OpenAI = _get_openai_client_class()

        client = OpenAI(
            api_key=engine_config.get("api_key"),
            base_url=engine_config.get("base_url", "https://api.deepseek.com"),
        )
        response = client.chat.completions.create(
            model=engine_config.get("model_name"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} if json_mode else None,
        )
        content = response.choices[0].message.content

    else:
        raise ValueError(f"Unsupported native SDK engine: {engine_choice}")

    if json_mode:
        return _parse_json_response(content)
    return content


def _call_ai_engine(
    engine_choice: str, config: Dict[str, Any], prompt: str, json_mode: bool = True
) -> Any:
    """
    Call the AI engine.

    Args:
        engine_choice: Selected engine
        config: Configuration dictionary
        prompt: AI prompt
        json_mode: Whether to use JSON mode

    Returns:
        AI response (dict/list if json_mode, else str)
    """
    engine_config = _get_engine_config(config, engine_choice)
    if not engine_config:
        raise ValueError(f"Engine configuration not found: {engine_choice}")

    # Built-in engines use direct HTTP calls so packaged builds do not need AI SDKs.
    if engine_choice == "gemini":
        try:
            return _call_gemini_http(engine_config, prompt, json_mode)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                print(f"⚠️ {engine_choice} Rate limited (429)")
            raise RuntimeError(f"AI call failed: {e}")

    if engine_choice == "deepseek":
        try:
            return _call_deepseek_http(engine_config, prompt, json_mode)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                print(f"⚠️ {engine_choice} Rate limited (429)")
            raise RuntimeError(f"AI call failed: {e}")

    if engine_choice == "ollama":
        try:
            return _call_ollama_http(engine_config, prompt, json_mode)
        except Exception as e:
            raise RuntimeError(f"AI call failed: {e}")

    # Custom providers use LiteLLM
    try:
        _get_litellm()
    except ImportError:
        pass
    else:
        try:
            return _call_via_litellm(engine_choice, engine_config, prompt, json_mode)
        except Exception as e:
            error_str = str(e)
            if (
                "429" in error_str
                or "RateLimit" in error_str
                or "quota" in error_str.lower()
            ):
                print(
                    f"⚠️ {engine_choice} Rate limited (429), falling back to native SDK..."
                )
            else:
                print(
                    f"LiteLLM call failed: {type(e).__name__}, falling back to native SDK..."
                )

    # Fallback to native SDK (even for custom providers as a last resort)
    try:
        return _call_via_native_sdk(engine_choice, engine_config, prompt, json_mode)
    except Exception as e:
        raise RuntimeError(f"AI call failed (LiteLLM & Native SDK): {e}")


def analyze_software_relation(
    engine_choice: str,
    config: Dict[str, Any],
    source_software: List[Dict[str, Any]],
    target_software: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Use AI to analyze relations between source software and target software.

    Args:
        engine_choice: AI Engine choice
        config: Configuration dictionary
        source_software: List of software from source directory
        target_software: List of software from target directory

    Returns:
        Grouped results containing matched software groups.
    """
    # File count limits to avoid Token overflow
    MAX_SOURCE_FILES = 80
    MAX_TARGET_FILES = 150

    # Truncate if too many files and log a warning
    truncated_source = (
        source_software[:MAX_SOURCE_FILES]
        if len(source_software) > MAX_SOURCE_FILES
        else source_software
    )

    # Intelligent Pre-filtering: Prioritize target files related to source files
    if len(target_software) > MAX_TARGET_FILES:
        truncated_target = _prefilter_target_files(
            truncated_source, target_software, MAX_TARGET_FILES
        )
        print(
            f"[AI Analysis] Too many target files ({len(target_software)}), intelligently filtered to {len(truncated_target)} related files"
        )
    else:
        truncated_target = target_software

    # Log warning if source files exceed limit
    if len(source_software) > MAX_SOURCE_FILES:
        print(
            f"[AI Analysis] Too many source files ({len(source_software)}), truncated to {MAX_SOURCE_FILES}"
        )

    # Construct compact prompt (optimized for Token consumption)
    source_info = "\n".join(
        [
            f"- {s['name']} [v{s['version'] or '?'}] ({s.get('extension', '')})"
            for s in truncated_source
        ]
    )

    target_info = (
        "\n".join(
            [
                f"- {t['name']} [v{t['version'] or '?'}] @ {t['parent_dir'] or '/'}"
                for t in truncated_target
            ]
        )
        if truncated_target
        else "(Empty)"
    )

    prompt = f"""Analyze the software list to identify different versions of the same software or products from the same series.

## Source Files (Pending processing):
{source_info}

## Target Files (Archived):
{target_info}

## Tasks
1. Identify correlations between source and target files representing the **same software** or **series**.
2. Examples: ON1.Effects and ON1.Photo.RAW are in the same series; 4K.Video.Downloader and 4K.YouTube.to.MP3 are in the same series.

## Output (JSON)
{{
    "groups": [
        {{
            "software_name": "Software/Series Name",
            "source_files": ["Source Filename 1"],
            "target_files": ["Matched Target Filename"],
            "latest_version": "Latest Version Filename"
        }}
    ],
    "unmatched": ["Unmatched Source Filenames"]
}}"""

    try:
        # _call_ai_engine returns a dict (since json_mode=True)
        result = _call_ai_engine(engine_choice, config, prompt, json_mode=True)
        return result
    except Exception as e:
        return {
            "error": str(e),
            "groups": [],
            "unmatched": [s["filename"] for s in source_software],
        }


def suggest_destination(
    engine_choice: str,
    config: Dict[str, Any],
    software_name: str,
    platform: str,
    existing_paths: List[str],
) -> Dict[str, Any]:
    """
    AI recommendation for software storage path (Cold start scenario).

    Args:
        engine_choice: AI Engine choice
        config: Configuration dictionary
        software_name: Software name
        platform: Platform type
        existing_paths: List of existing paths in the target directory

    Returns:
        Path suggestions dictionary.
    """
    paths_info = (
        "\n".join([f"- {p}" for p in existing_paths])
        if existing_paths
        else "(Directory Empty)"
    )

    prompt = f"""You are a software classification expert. Please suggest a storage path for the following software.

## Software Information
- Name: {software_name}
- Platform: {platform.upper()}

## Existing paths in target directory:
{paths_info}

## Tasks
1. Determine the software type based on its name (e.g., Development Tools, Office, Multimedia, etc.).
2. Select the most suitable existing path or suggest creating a new one.

## Output Format (JSON)
{{
    "suggested_paths": [
        {{"path": "Path 1", "reason": "Reason for suggestion"}},
        {{"path": "Path 2", "reason": "Reason for suggestion"}}
    ],
    "create_new": {{
        "recommended": true/false,
        "path": "Suggested new path name",
        "reason": "Reason"
    }}
}}"""

    try:
        # _call_ai_engine returns a dict
        result = _call_ai_engine(engine_choice, config, prompt, json_mode=True)
        return result
    except Exception as e:
        return {
            "error": str(e),
            "suggested_paths": [],
            "create_new": {"recommended": False},
        }


def _prefilter_target_files(
    source_software: List[Dict[str, Any]],
    target_software: List[Dict[str, Any]],
    max_files: int = 150,
) -> List[Dict[str, Any]]:
    """
    Pre-filter relevant target files based on source filenames.

    Args:
        source_software: List of source software
        target_software: List of target software
        max_files: Maximum number of files to return

    Returns:
        Filtered list of target software.
    """
    # Extract keywords from source files
    keywords = set()
    for s in source_software:
        name = s.get("name", "").lower()
        if name:
            # Tokenize: Split by space, underscore, hyphen, dot
            for word in re.split(r"[\s_\-\.]+", name):
                if len(word) >= 2:  # Ignore single characters
                    keywords.add(word)

    # Match keywords in target files
    matched = []
    unmatched = []

    for t in target_software:
        target_name = t.get("name", "").lower()
        target_filename = t.get("filename", "").lower()
        search_text = f"{target_name} {target_filename}"

        if any(kw in search_text for kw in keywords):
            matched.append(t)
        else:
            unmatched.append(t)

    # If matched results are insufficient, complement with unmatched files
    if len(matched) < max_files:
        matched.extend(unmatched[: max_files - len(matched)])

    return matched[:max_files]


def suggest_best_directory(
    software_name: str,
    target_software: List[Dict[str, Any]],
    level1_directories: List[str],
) -> Optional[str]:
    """
    Smart recommendation for best directory location (for software without precise matches).

    Matching Strategy:
    1. Extract vendor/brand keywords from software name (e.g., Adobe, ON1, 4K).
    2. Search for target files containing the same keywords.
    3. Return the Level-1 directory with the most matching files.
    4. Return None if no match is found.

    Args:
        software_name: Software name to match
        target_software: All software items in the target directory
        level1_directories: List of absolute paths for Level-1 directories

    Returns:
        Suggested directory path, or None.
    """
    if not software_name or not target_software:
        return None

    from .file_ops import normalize_software_name

    # 1. Extract software name keywords (brand/vendor usually the first word)
    normalized_name = normalize_software_name(software_name)
    words = normalized_name.split()

    # Get valid keywords (length >= 2, exclude version numbers and common stop words)
    skip_words = {
        "pro",
        "mac",
        "win",
        "windows",
        "osx",
        "app",
        "the",
        "for",
        "and",
        "or",
    }
    keywords = []
    for word in words:
        if len(word) >= 2 and word not in skip_words and not word.isdigit():
            keywords.append(word)

    if not keywords:
        return None

    # 2. Search for target files containing the same keywords
    # Calculate scores for each Level-1 directory
    dir_scores = {}  # {level1_dir: score}

    for t in target_software:
        target_name = normalize_software_name(t.get("name", ""))
        target_filename = normalize_software_name(
            t.get("filename", ""), strip_extension=True
        )

        # Use 'path' to get absolute directory, as 'parent_dir_abs' is not available in scan results
        file_path = t.get("path", "")
        if not file_path:
            continue

        # Get absolute parent directory
        abs_parent_dir = os.path.dirname(file_path)

        # Determine which Level-1 directory this file belongs to
        matched_level1 = None
        for level1 in sorted(level1_directories, key=len, reverse=True):
            # Check if file is inside this level1 directory
            if abs_parent_dir == level1 or abs_parent_dir.startswith(level1 + os.sep):
                matched_level1 = level1
                break

        if not matched_level1:
            continue

        # Calculate match score (number of matching keywords)
        search_text = f"{target_name} {target_filename}"
        score = sum(1 for kw in keywords if kw in search_text)

        # First keyword (usually the brand name) gets higher weight
        if keywords and keywords[0] in search_text:
            score += 2

        if score > 0:
            dir_scores[matched_level1] = dir_scores.get(matched_level1, 0) + score

    # 3. Return the directory with the highest score
    if dir_scores:
        # Find directory with max score
        best_dir = max(dir_scores.items(), key=lambda x: x[1])[0]
        return best_dir

    return None


def suggest_directory_by_category(
    software_name: str,
    level1_directories: List[str],
    common_categories: Dict[str, List[str]] = None,
) -> Optional[str]:
    """
    Recommend directory based on software type (pre-defined category rules).

    Args:
        software_name: Software name
        level1_directories: List of Level-1 directories
        common_categories: Custom category rules {dir_keyword: [software_keywords]}

    Returns:
        Suggested directory path, or None.
    """
    if not common_categories:
        # Default category rules
        common_categories = {
            "pdf": ["pdf", "ocr", "abbyy"],
            "read": ["epub", "ebook", "book", "reader", "chm", "calibre"],
            "security": [
                "password",
                "encrypt",
                "security",
                "1password",
                "auth",
                "vault",
            ],
            "finder": ["finder", "file", "commander", "rename", "qspace"],
            "touchpad": ["touch", "gesture", "trackpad", "mouse", "rectangle"],
            "phone": [
                "ios",
                "iphone",
                "ipad",
                "ipa",
                "android",
                "mobile",
                "imazing",
                "iexplorer",
                "i4tools",
                "phoneclean",
            ],
            "aigc": [
                "ai",
                "chatgpt",
                "claude",
                "gemini",
                "diffusion",
                "stable",
                "midjourney",
            ],
            "live": [
                "chat",
                "wechat",
                "telegram",
                "teams",
                "game",
                "emulator",
                "playcover",
                "dolphin",
                "rpcs3",
                "epic",
                "steam",
            ],
            "system": [
                "clean",
                "disk",
                "memory",
                "monitor",
                "utility",
                "tool",
                "backup",
                "archive",
                "compress",
                "zip",
                "uninstaller",
                "password",
                "finder",
                "virtual",
                "vm",
            ],
            "office": [
                "office",
                "word",
                "excel",
                "note",
                "document",
                "markdown",
                "mind",
                "xmind",
                "write",
                "text",
            ],
            "design": [
                "photo",
                "image",
                "draw",
                "paint",
                "design",
                "sketch",
                "graphic",
                "adobe",
                "photoshop",
                "illustrator",
                "affinity",
                "figma",
                "topaz",
            ],
            "media": [
                "video",
                "audio",
                "music",
                "player",
                "movie",
                "media",
                "converter",
                "screen",
                "record",
                "youtube",
            ],
            "net": [
                "download",
                "browser",
                "ftp",
                "vpn",
                "proxy",
                "network",
                "ssh",
                "remote",
            ],
            "dev": [
                "code",
                "editor",
                "ide",
                "git",
                "database",
                "sql",
                "terminal",
                "docker",
                "postman",
            ],
        }

    from .file_ops import normalize_software_name

    name_lower = f"{software_name.lower()} {normalize_software_name(software_name)}"

    for dir_keyword, software_keywords in common_categories.items():
        if any(kw in name_lower for kw in software_keywords):
            # Search for Level-1 directory containing the keyword
            for level1 in level1_directories:
                dir_name = os.path.basename(level1).lower()
                if dir_keyword in dir_name:
                    return level1

    return None


def group_software_by_name(
    software_list: List[Dict[str, Any]],
    cross_format_match: bool = False,
) -> Dict[str, List[Dict]]:
    """
    Group software locally based on parsed name and extension (no AI call).

    If cross_format_match is True, extension differences are ignored.
    Otherwise, items are grouped only if both name and extension match.

    Args:
        software_list: List of software items
        cross_format_match: Whether to perform cross-format matching

    Returns:
        Dictionary grouped by name (+extension).
    """
    from .file_ops import artifact_variant, normalize_software_name

    groups = {}

    for software in software_list:
        name = normalize_software_name(software.get("name", ""))
        if not name:
            name = normalize_software_name(
                software.get("filename", ""), strip_extension=True
            )

        parent_identity = ""
        if not name or name in {"autoupdate", "download", "install", "installer", "launcher", "setup", "uninstall", "update", "updater"}:
            parent_identity = os.path.realpath(
                software.get("parent_dir") or os.path.dirname(software.get("path", ""))
            )
            name = name or "generic"

        # Get extension
        extension = software.get("extension", "").lower()
        variant = artifact_variant(software.get("filename", software.get("name", "")))

        # Determine grouping key
        if cross_format_match:
            # Cross-format: Use name only
            group_key = f"{name}_{variant}_{parent_identity}"
        else:
            # Strict: Use "name_extension"
            group_key = f"{name}_{extension}_{variant}_{parent_identity}"

        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(software)

    # Sort by parsed numeric version, then modification time for unversioned files.
    for group_key in groups:
        groups[group_key].sort(
            key=lambda item: (
                bool(item.get("version")),
                tuple(int(part) for part in re.findall(r"\d+", item.get("version") or "")),
                item.get("mtime", 0) or item.get("modified", 0) or 0,
            ),
            reverse=True,
        )

    return groups


def compare_versions(v1: Optional[str], v2: Optional[str]) -> int:
    """
    Compare two version numbers.

    Args:
        v1: Version 1
        v2: Version 2

    Returns:
        1 if v1 > v2, -1 if v1 < v2, 0 if equal.
    """
    if not v1 and not v2:
        return 0
    if not v1:
        return -1
    if not v2:
        return 1

    def parse_version(v: str) -> List[int]:
        return [int(x) for x in re.findall(r"\d+", v)]

    parts1 = parse_version(v1)
    parts2 = parse_version(v2)

    for p1, p2 in zip(parts1, parts2):
        if p1 > p2:
            return 1
        if p1 < p2:
            return -1

    return len(parts1) - len(parts2)


def analyze_duplicate_groups(
    engine_choice: str,
    config: Dict[str, Any],
    groups: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Use AI to analyze duplicate software groups and provide keep recommendations.

    Args:
        engine_choice: AI Engine choice
        config: Configuration dictionary
        groups: List of duplicate groups (containing a 'files' list)

    Returns:
        Dict: {
            "recommendations": [
                {
                    "group_name": "Software Name",
                    "keep_indices": [0],  # Indices of files recommended to keep
                    "reason": "Retention reason (e.g., latest version)"
                }
            ]
        }
    """
    # Limit groups per batch to avoid Context Window overflow
    MAX_GROUPS = 50
    processed_groups = groups[:MAX_GROUPS]

    groups_text = []
    for i, group in enumerate(processed_groups):
        files_info = []
        for j, file in enumerate(group["files"]):
            # Format: [0] filename (v1.0) - 50MB
            size_mb = file.get("size", 0) / (1024 * 1024)
            flags = []
            if file.get("retention_protected"):
                flags.append("PROTECTED")
            if file.get("manual_keep") is True:
                flags.append("MANUAL_KEEP")
            elif file.get("manual_keep") is False:
                flags.append("MANUAL_SKIP")
            flag_text = f" [{' '.join(flags)}]" if flags else ""
            info = (
                f"[{j}] {file['filename']} (v{file.get('version') or '?'})"
                f" - {size_mb:.1f}MB{flag_text}"
            )
            files_info.append(info)

        group_text = f"Group {i} ({group['software_name']}):\n" + "\n".join(files_info)
        groups_text.append(group_text)

    prompt = f"""Analyze the following duplicate software groups and recommend which version to keep.

{chr(10).join(groups_text)}

## Task
For each group, determine which file is most worth keeping (usually the latest version or the most complete file).
Never recommend deleting files marked PROTECTED. Respect MANUAL_KEEP and MANUAL_SKIP unless there is a clear risk.

## Output (JSON)
{{
    "recommendations": [
        {{
            "group_index": 0,
            "keep_indices": [0],
            "reason": "Short reason (e.g., keep latest version v2.5, delete v2.0)"
        }}
    ]
}}"""

    try:
        return _call_ai_engine(engine_choice, config, prompt, json_mode=True)
    except Exception as e:
        return {"error": str(e), "recommendations": []}


def batch_analyze_path_suggestions(
    engine_choice: str,
    config: Dict[str, Any],
    software_list: List[Dict[str, Any]],
    available_directories: List[str],
) -> Dict[str, Any]:
    """
    Use AI to intelligently categorize multiple new software into the most suitable directories.

    Args:
        engine_choice: AI Engine choice
        config: Configuration dictionary
        software_list: List of software info dictionaries (source files)
        available_directories: List of absolute paths for existing target folders

    Returns:
        Dict: {
            "suggestions": [
                {
                    "filename": "Software.dmg",
                    "suggested_path": "/path/to/BestFolder",
                    "reason": "Why it fits here"
                }
            ]
        }
    """
    if not software_list or not available_directories:
        return {"suggestions": []}

    # Prepare data for AI
    sw_info = []
    for s in software_list:
        sw_info.append(f"- {s['filename']} (Name: {s.get('name', 'Unknown')})")

    # Send stable local IDs instead of absolute paths. The server maps IDs back
    # to local directories after the model responds.
    directory_lookup = {}
    dir_info = []
    for index, directory in enumerate(available_directories, start=1):
        directory_id = f"DIR_{index:03d}"
        directory_lookup[directory_id] = directory
        label = os.path.basename(os.path.normpath(directory)) or "ROOT"
        dir_info.append(f"- {directory_id}: {label}")

    prompt = f"""You are a macOS/Software administration expert. Your task is to categorize the following NEW software into the most appropriate EXISTING folders.

## NEW SOFTWARE TO CATEGORIZE:
{chr(10).join(sw_info)}

## AVAILABLE TARGET FOLDERS:
{chr(10).join(dir_info)}

## INSTRUCTIONS:
1. Analyze each software's name and extension to understand its function (e.g., Development, Design, Utility, Media).
2. Match it with the most semantically related folder from the provided list.
3. If multiple folders seem relevant, pick the most specific one.
4. If NO folder is suitable, suggest the "ROOT" (which means the base category folder).
5. Return the directory ID (for example, "DIR_001") in "suggested_path". Never return an absolute filesystem path.

## OUTPUT FORMAT (JSON):
{{
    "suggestions": [
        {{
            "filename": "Exact Filename from list",
            "suggested_path": "DIR_001 from available folders OR 'ROOT'",
            "reason": "Short reason in Chinese"
        }}
    ]
}}"""

    try:
        result = _call_ai_engine(engine_choice, config, prompt, json_mode=True)
        for suggestion in result.get("suggestions", []):
            directory_id = str(suggestion.get("suggested_path", "")).strip()
            if directory_id in directory_lookup:
                suggestion["suggested_path"] = directory_lookup[directory_id]
        return result
    except Exception as e:
        print(f"Batch path suggestion failed: {e}")
        return {"error": str(e), "suggestions": []}
