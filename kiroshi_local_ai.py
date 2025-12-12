import os
import streamlit as st
import sys

# Directory where models are stored
MODELS_DIR = os.path.join(os.getcwd(), "models")
os.makedirs(MODELS_DIR, exist_ok=True)

# Configuration for available models
MODELS = {
    "speed": {
        "repo_id": "microsoft/Phi-3-mini-4k-instruct-gguf",
        "filename": "Phi-3-mini-4k-instruct-q4.gguf",
        "name": "Speed (Phi-3 Mini)",
        "ctx_size": 4096,
        "chat_format": "phi-3"
    },
    "quality": {
        "repo_id": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "name": "Quality (Llama 3.1 8B)",
        "ctx_size": 8192,
        "chat_format": "llama-3"
    }
}

# Global cache for the loaded model instance
if "local_llm_instance" not in st.session_state:
    st.session_state.local_llm_instance = None
if "local_llm_profile" not in st.session_state:
    st.session_state.local_llm_profile = None

def get_model_path(profile: str) -> str:
    """Returns the full path to the model file."""
    config = MODELS.get(profile)
    if not config:
        raise ValueError(f"Unknown profile: {profile}")
    return os.path.join(MODELS_DIR, config["filename"])

def check_model_exists(profile: str) -> bool:
    """Checks if the model file is already downloaded."""
    path = get_model_path(profile)
    return os.path.exists(path)

def download_model(profile: str, progress_callback=None):
    """Downloads the model file from HuggingFace."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise RuntimeError("huggingface_hub not installed. Cannot download models.")

    config = MODELS.get(profile)
    if not config:
        raise ValueError(f"Unknown profile: {profile}")

    print(f"Downloading {config['name']}...")
    try:
        file_path = hf_hub_download(
            repo_id=config["repo_id"],
            filename=config["filename"],
            local_dir=MODELS_DIR,
            local_dir_use_symlinks=False
        )
        return file_path
    except Exception as e:
        raise RuntimeError(f"Failed to download model: {e}")

def load_model(profile: str):
    """Loads the model into memory. Returns Llama instance."""
    try:
        from llama_cpp import Llama
    except ImportError:
        raise RuntimeError("llama-cpp-python not installed. Cannot run local models.")

    # Check if we already have this model loaded
    if st.session_state.local_llm_instance is not None:
        if st.session_state.local_llm_profile == profile:
            return st.session_state.local_llm_instance
        else:
            # Unload previous model
            print("Unloading previous model...")
            del st.session_state.local_llm_instance
            st.session_state.local_llm_instance = None
            import gc
            gc.collect()

    path = get_model_path(profile)
    if not os.path.exists(path):
         raise FileNotFoundError(f"Model file not found: {path}")

    config = MODELS[profile]

    print(f"Loading model {profile} from {path}...")

    # Try to use GPU if available, otherwise CPU
    # n_gpu_layers=-1 means offload all layers if possible.
    try:
        llm = Llama(
            model_path=path,
            n_ctx=config["ctx_size"],
            n_gpu_layers=-1,
            verbose=False
        )
    except Exception:
        # Fallback to CPU only if GPU init fails (e.g. CUDA libs missing)
        print("GPU initialization failed, falling back to CPU...")
        llm = Llama(
            model_path=path,
            n_ctx=config["ctx_size"],
            n_gpu_layers=0,
            verbose=False
        )

    st.session_state.local_llm_instance = llm
    st.session_state.local_llm_profile = profile
    return llm

def generate_response(messages: list, profile: str) -> str:
    """Generates a response from the loaded model."""
    llm = load_model(profile)

    response = llm.create_chat_completion(
        messages=messages,
        temperature=0.7,
        max_tokens=1024, # Reasonable limit
        stop=["<|eot_id|>", "<|end|>", "<|user|>", "</s>"] # Safety stops
    )

    return response["choices"][0]["message"]["content"]
