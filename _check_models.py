from fastembed import TextEmbedding
from huggingface_hub import HfApi

ms = TextEmbedding.list_supported_models()
print("=== ALL SUPPORTED MODELS ===")
for m in ms:
    name = m["model"]
    desc = m.get("description", "")
    print(f'{name:55s} dim={m["dim"]:4d}  {desc}')

print("\n=== MULTILINGUAL / JAPANESE ===")
for m in ms:
    name = m["model"]
    if any(k in name.lower() for k in ["multilingual", "japanese", "xlm-roberta", "paraphrase"]):
        print(f'{name:55s} dim={m["dim"]:4d}')
