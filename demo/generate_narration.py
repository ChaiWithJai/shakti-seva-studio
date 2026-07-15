"""Generate the demo voice with Liquid LFM2.5 Audio on the CPU."""

from __future__ import annotations

import argparse
from pathlib import Path

import soundfile as sf
import torch
from liquid_audio import ChatState, LFM2AudioModel, LFM2AudioProcessor


ROOT = Path(__file__).resolve().parent
MODEL = "LiquidAI/LFM2.5-Audio-1.5B"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", type=Path, default=ROOT / "narration.txt")
    parser.add_argument("--output", type=Path, default=ROOT / "public" / "narration.wav")
    args = parser.parse_args()

    paragraphs = [" ".join(part.split()) for part in args.text.read_text(encoding="utf-8").split("\n\n") if part.strip()]
    processor = LFM2AudioProcessor.from_pretrained(MODEL, device="cpu").eval()
    model = LFM2AudioModel.from_pretrained(MODEL, device="cpu").eval()
    # liquid-audio 1.3.0 honors device="cpu" during generation, but its lazy
    # LFM detokenizer still calls Module.cuda(). Keep that one construction on
    # CPU until the package carries its selected device into the decoder.
    original_cuda = torch.nn.Module.cuda
    torch.nn.Module.cuda = lambda module, *unused_args, **unused_kwargs: module
    clips: list[torch.Tensor] = []
    try:
        for index, text in enumerate(paragraphs, start=1):
            chat = ChatState(processor)
            chat.new_turn("system")
            chat.add_text("Perform TTS. Use the US female voice. Speak clearly at a measured pace.")
            chat.end_turn()
            chat.new_turn("user")
            chat.add_text(text)
            chat.end_turn()
            chat.new_turn("assistant")

            audio_out: list[torch.Tensor] = []
            with torch.inference_mode():
                for token in model.generate_sequential(
                    **chat,
                    max_new_tokens=900,
                    audio_temperature=0.8,
                    audio_top_k=64,
                ):
                    if token.numel() > 1:
                        audio_out.append(token)
            if len(audio_out) < 2:
                raise RuntimeError(f"Liquid Audio did not return enough audio tokens for paragraph {index}")
            codes = torch.stack(audio_out[:-1], 1).unsqueeze(0)
            clips.append(processor.decode(codes).cpu()[0])
            print(f"paragraph {index}/{len(paragraphs)}")
    finally:
        torch.nn.Module.cuda = original_cuda
    pause = torch.zeros(8_400)
    waveform = torch.cat([part for clip in clips for part in (clip, pause)])[:-len(pause)].numpy()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.output, waveform, 24_000)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
