"""Which Habibi-TTS weights exist and how to fetch them. Light on purpose: the Modal image bakes weights with it."""
from huggingface_hub import hf_hub_download

REPO = "SWivid/Habibi-TTS"
VOCODER_REPO = "charactr/vocos-mel-24khz"
VOCODER_FILES = ("config.yaml", "pytorch_model.bin")

APACHE = "Apache-2.0"  # commercial use OK
NON_COMMERCIAL = "CC-BY-NC-SA-4.0"  # non-commercial only (trained on SADA / Mixat)

# name -> (checkpoint, vocab, takes a dialect tag, weights license).
# Specialized models speak one dialect and ignore the tag. Only "unified" reads it.
MODELS = {
    "mar": ("Specialized/MAR/model_100000.safetensors", "Specialized/MAR/vocab.txt", False, APACHE),  # Moroccan Darija
    "msa": ("Specialized/MSA/model_200000.safetensors", "Specialized/MSA/vocab.txt", False, APACHE),  # Modern Standard Arabic
    "egy": ("Specialized/EGY/model_100000.safetensors", "Specialized/EGY/vocab.txt", False, APACHE),  # Egyptian
    "alg": ("Specialized/ALG/model_100000.safetensors", "Specialized/ALG/vocab.txt", False, APACHE),  # Algerian
    "irq": ("Specialized/IRQ/model_100000.safetensors", "Specialized/IRQ/vocab.txt", False, APACHE),  # Iraqi
    "sau": ("Specialized/SAU/model_200000.safetensors", "Specialized/SAU/vocab.txt", False, NON_COMMERCIAL),  # Saudi / Gulf
    "uae": ("Specialized/UAE/model_100000.safetensors", "Specialized/UAE/vocab.txt", False, NON_COMMERCIAL),  # Emirati
    "unified": ("Unified/model_200000.safetensors", "Unified/vocab.txt", True, NON_COMMERCIAL),  # 12 dialects via tag
}
DEFAULT_MODEL = "mar"


def download(model: str) -> tuple[str, str]:
    """Return local (checkpoint, vocab) paths, downloading into the HF cache if needed."""
    ckpt, vocab, *_ = MODELS[model]
    return hf_hub_download(REPO, ckpt), hf_hub_download(REPO, vocab)


def download_vocoder() -> None:
    for name in VOCODER_FILES:
        hf_hub_download(VOCODER_REPO, name)
