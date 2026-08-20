"""
Model management — pull models from Ollama registry or HuggingFace.
"""

import subprocess
import sys
import logging

logger = logging.getLogger(__name__)


RECOMMENDED_MODELS = {
    # Best for tool calling / agentic use
    "agentic": [
        ("qwen2.5:7b", "Top choice for tool calling. 7B params, needs ~8GB RAM."),
        ("qwen2.5:14b", "Higher quality tool calling. 14B params, needs ~16GB RAM."),
        ("llama3.1:8b", "Excellent reasoning + tool selection. 8B params, needs ~8GB RAM."),
        ("mistral:7b", "Good logic parsing, consistent tool output. 7B params, needs ~8GB RAM."),
        ("qwen2.5-coder:7b", "Specialized for coding tasks with tool calling."),
    ],
    # For low-end hardware
    "small": [
        ("llama3.2:3b", "Compact model. 3B params, needs ~4GB RAM."),
        ("llama3.2:1b", "Tiny model. 1B params, needs ~2GB RAM."),
        ("qwen2.5:3b", "Small Qwen with tool calling support."),
    ],
    # High quality (needs GPU)
    "high_quality": [
        ("llama3.1:70b", "Best quality. 70B params, needs ~48GB VRAM."),
        ("llama3.3:70b", "Latest Llama 3.3. 70B params, needs ~48GB VRAM."),
        ("qwen2.5:32b", "Large Qwen. 32B params, needs ~24GB RAM."),
    ],
    # HuggingFace GGUF models
    "huggingface": [
        ("hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M", "Llama 3.2 3B from HuggingFace (Q4 quantization)."),
        ("hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF:Q4_K_M", "Qwen 2.5 7B from HuggingFace (Q4 quantization)."),
        ("hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Q4_K_M", "Phi-3 Mini from HuggingFace. Compact and capable."),
    ],
}


def list_models() -> dict:
    """List all available model recommendations."""
    return RECOMMENDED_MODELS


def pull_model(model_name: str, progress_callback=None):
    """Pull a model via Ollama. Works with both Ollama registry and HuggingFace models."""
    try:
        process = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        
        for line in process.stdout:
            line = line.strip()
            if line and progress_callback:
                progress_callback(line)
            elif line:
                print(f"  {line}")
        
        process.wait()
        return process.returncode == 0
    except FileNotFoundError:
        print("✗ Ollama not found. Install it first: https://ollama.com/download")
        return False
    except Exception as e:
        logger.error(f"Error pulling model: {e}")
        return False


def interactive_model_setup():
    """Interactive CLI to choose and pull a model."""
    print("\n    ◈  Model Setup\n")
    print("    Choose a category:\n")
    
    categories = list(RECOMMENDED_MODELS.keys())
    for i, cat in enumerate(categories, 1):
        print(f"    {i}. {cat.replace('_', ' ').title()}")
    print()
    
    try:
        choice = int(input("    Select category (1-{}): ".format(len(categories))))
        if choice < 1 or choice > len(categories):
            print("    Invalid choice.")
            return
    except (ValueError, EOFError):
        print("    Invalid input.")
        return
    
    category = categories[choice - 1]
    models = RECOMMENDED_MODELS[category]
    
    print(f"\n    Models in '{category}':\n")
    for i, (name, desc) in enumerate(models, 1):
        print(f"    {i}. {name}")
        print(f"       {desc}")
    print()
    
    try:
        model_choice = int(input("    Select model (1-{}): ".format(len(models))))
        if model_choice < 1 or model_choice > len(models):
            print("    Invalid choice.")
            return
    except (ValueError, EOFError):
        print("    Invalid input.")
        return
    
    model_name = models[model_choice - 1][0]
    print(f"\n    Pulling {model_name}...")
    print(f"    (This may take a while depending on model size and your connection)\n")
    
    success = pull_model(model_name)
    if success:
        print(f"\n    ✓ Model '{model_name}' pulled successfully!")
        print(f"    Update your config/config.yaml to use this model.")
    else:
        print(f"\n    ✗ Failed to pull model.")
    
    return model_name if success else None


def import_huggingface_model(repo_id: str, gguf_filename: str = None, 
                              quantization: str = "Q4_K_M", custom_name: str = None):
    """
    Import a model from HuggingFace that's not in the Ollama registry.
    
    Args:
        repo_id: HuggingFace repo ID (e.g. 'username/model-name')
        gguf_filename: Specific GGUF filename (if repo has multiple)
        quantization: Quantization level (Q4_K_M, Q5_K_M, Q8_0, etc.)
        custom_name: Custom name for the model in Ollama
    """
    # Build the HuggingFace pull identifier
    hf_id = f"hf.co/{repo_id}:{quantization}"
    
    print(f"    Pulling {hf_id} from HuggingFace...")
    success = pull_model(hf_id)
    
    if success and custom_name:
        # Create a Modelfile alias
        import tempfile
        import os
        
        modelfile_content = f"FROM {hf_id}\n"
        modelfile_path = os.path.join(tempfile.gettempdir(), f"{custom_name}.modelfile")
        
        with open(modelfile_path, "w") as f:
            f.write(modelfile_content)
        
        try:
            subprocess.run(["ollama", "create", custom_name, "-f", modelfile_path], check=True)
            print(f"\n    ✓ Model '{custom_name}' created from {repo_id}")
        except subprocess.CalledProcessError:
            print(f"\n    ⚠ Model pulled but could not create alias. Use '{hf_id}' as model name.")
    elif success:
        print(f"\n    ✓ Model pulled. Use '{hf_id}' as the model name in config.")
    else:
        print(f"\n    ✗ Failed to pull model from HuggingFace.")
    
    return success


if __name__ == "__main__":
    interactive_model_setup()
