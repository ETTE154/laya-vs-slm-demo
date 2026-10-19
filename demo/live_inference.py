"""Single-input local comparison. Independent of the frozen benchmark runner."""
from pathlib import Path
import copy
import os
import threading
import time
from shared_task import COMMON_INSTRUCTION, parse_task

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
ROOT = Path(__file__).resolve().parent
MODEL_ORDER = ("laya", "llama1b", "llama3b")
NAMES = {"laya": "Laya · 제로샷 분류", "llama1b": "Llama 3.2 · 1B", "llama3b": "Llama 3.2 · 3B"}
HEAD_BUDGET = 640


class SharedTaskLimitError(ValueError):
    """Abort every model rather than compare differently truncated tasks."""


class LiveEngines:
    def __init__(self, threads=8):
        self.threads = threads
        self.models = {}
        self.tokenizers = {}
        self.configs = {}
        self.load_times = {}
        self.runtime_ready = False
        self.run_lock = threading.Lock()

    def metadata(self):
        return {
            "app": "local-comparison-v3", "device": "cpu", "threads": self.threads,
            "models": [{"key": key, "name": NAMES[key], "kind": "classification" if key == "laya" else "generation",
                        "ready": key in self.load_times} for key in MODEL_ORDER],
            "task_mode": "shared_multiple_choice", "instruction": COMMON_INSTRUCTION,
            "fixed_candidates": False, "max_input_chars": 2000, "max_new_tokens": 16,
            "candidate_count": {"min": 2, "max": 10},
            "candidate_laya_token_limit": 48,
            "metadata": {"model": "convaiinnovations/laya (English)"},
            "timing": "Model load excluded. TTFT includes tokenization and prefill. Decode tok/s=(generated tokens-1)/(last token time-first token time); EOS counted. Laya generates no tokens.",
        }

    def load(self, key, emit):
        if key in self.load_times:
            return 0.0
        begin = time.perf_counter()
        emit({"type": "status", "model": key, "message": "로컬 모델을 불러오는 중…"})
        if not self.runtime_ready:
            import torch
            import transformers
            self.torch, self.transformers = torch, transformers
            torch.set_num_threads(self.threads)
            torch.set_num_interop_threads(1)
            self.runtime_ready = True
        if key == "laya":
            import laya
            self.classifier = laya.load(str(ROOT.parent / "models/laya"), device="cpu", backend="eager")
        else:
            model_path = ROOT.parent / "models" / key
            tokenizer = self.transformers.AutoTokenizer.from_pretrained(str(model_path), local_files_only=True, trust_remote_code=False)
            model = self.transformers.AutoModelForCausalLM.from_pretrained(
                str(model_path), local_files_only=True, trust_remote_code=False,
                dtype=self.torch.float32, attn_implementation="sdpa").eval()
            cfg = copy.deepcopy(model.generation_config)
            cfg.do_sample = False
            cfg.num_beams = 1
            cfg.temperature = 1.0
            cfg.top_p = 1.0
            cfg.max_new_tokens = 16
            cfg.use_cache = True
            cfg.pad_token_id = tokenizer.pad_token_id
            self.models[key], self.tokenizers[key], self.configs[key] = model, tokenizer, cfg
        elapsed = (time.perf_counter() - begin) * 1000
        self.load_times[key] = elapsed
        print("Ready:", key, round(elapsed, 1), "ms", flush=True)
        return elapsed

    def classify(self, task, load_ms, emit):
        from laya.common import build_head, render_options, _encode_question_text
        begin = time.perf_counter()
        q = {"t": "choice", "ins": task["instruction"], "crit": task["choices"]}
        tok = self.classifier.tok
        if any(tok.mask_token in value for value in [task["question"], *task["choices"].values()]):
            raise SharedTaskLimitError("모델 특수 토큰은 질문과 보기에 사용할 수 없습니다.")
        # Laya silently caps each rendered option to 48 tokens. Detect any loss
        # before a forward pass so all models receive the complete same task.
        ids, markers, _ = build_head(tok, q, HEAD_BUDGET)
        full_instruction = len(_encode_question_text(tok, "choice question: " + q["ins"], add_special_tokens=False))
        if len(markers) != len(task["choices"]) or markers[0] - 2 != full_instruction:
            raise SharedTaskLimitError("공통 지시문을 모두 전달할 수 없습니다. 보기 수나 길이를 줄여 주세요.")
        for index, (label, option) in enumerate(zip(task["choices"], render_options(q))):
            full_option = len(_encode_question_text(tok, " " + option, add_special_tokens=False))
            end = markers[index + 1] if index + 1 < len(markers) else len(ids) - 1
            if end - markers[index] - 1 != full_option:
                raise SharedTaskLimitError(f"보기 {label}가 Laya의 48토큰 한도를 넘습니다. 세 모델에 같은 내용을 전달하도록 보기를 줄여 주세요.")
        raw = self.classifier.predict(
            task["question"], {"answer": {"type": "choice", "instructions": task["instruction"], "criteria": task["choices"]}},
            max_len=4096, head_max_len=HEAD_BUDGET)
        elapsed = (time.perf_counter() - begin) * 1000
        usage = raw["usage"]
        if usage.get("truncated") or usage.get("options"):
            raise SharedTaskLimitError("공통 입력 길이를 초과했습니다. 세 모델에 같은 내용을 전달하도록 입력을 줄여 주세요.")
        answer = raw["answers"]["answer"]
        ranked = sorted(answer["probabilities"].items(), key=lambda x: x[1], reverse=True)
        selected = str(answer["choice"])
        valid = selected in task["choices"]
        emit({"type": "model_result", "model": "laya", "kind": "classification",
              "task_sha256": task["task_sha256"], "label": selected if valid else None,
              "answer": task["choices"].get(selected), "valid_choice": valid,
              "scores": [{"label": k, "answer": task["choices"].get(k), "score": float(v)} for k, v in ranked],
              "text": selected, "latency_ms": round(elapsed, 3), "load_ms": round(load_ms, 3),
              "input_tokens": usage["input_tokens"], "output_tokens": 0,
              "ttft_ms": None, "tokens_per_second": None, "generation_ms": None, "finish_reason": "classification"})

    def generate(self, key, task, load_ms, emit):
        from transformers import TextStreamer
        tokenizer, model, cfg = self.tokenizers[key], self.models[key], self.configs[key]
        begin = time.perf_counter()
        # The same question, answer candidates, and instruction as the classifier.
        content = task["question"] + "\n\nCandidates:\n" + "\n".join(f"{key}. {value}" for key, value in task["choices"].items())
        messages = [{"role": "system", "content": task["instruction"]}, {"role": "user", "content": content}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, date_string="19 October 2026")
        inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False, truncation=False)
        input_tokens = inputs["input_ids"].shape[1]
        if input_tokens + cfg.max_new_tokens > min(4096, model.config.max_position_embeddings):
            raise ValueError("SLM 입력 길이를 초과했습니다. 입력을 줄여 주세요.")

        class MeasuredStreamer(TextStreamer):
            def __init__(self):
                super().__init__(tokenizer, skip_prompt=True, skip_special_tokens=True, clean_up_tokenization_spaces=False)
                self.count = 0
                self.first = None
                self.last = None
                self.pieces = []

            def put(self, value):
                if not self.next_tokens_are_prompt:
                    now = time.perf_counter()
                    self.first = self.first if self.first is not None else now
                    self.last = now
                    self.count += value.numel()
                super().put(value)

            def metrics(self):
                span = self.last - self.first if self.first is not None and self.last is not None else 0
                return {"output_tokens": self.count,
                        "elapsed_ms": round((time.perf_counter() - begin) * 1000, 3),
                        "ttft_ms": round((self.first - begin) * 1000, 3) if self.first is not None else None,
                        "tokens_per_second": round((self.count - 1) / span, 3) if self.count > 1 and span > 0 else None,
                        "generation_ms": round(span * 1000, 3) if self.first is not None else None}

            def on_finalized_text(self, chunk, stream_end=False):
                self.pieces.append(chunk)
                emit({"type": "token", "model": key, "text": chunk, **self.metrics()})

        streamer = MeasuredStreamer()
        with self.torch.inference_mode():
            output = model.generate(**inputs, generation_config=cfg, streamer=streamer)
        generated = output[0, input_tokens:].tolist()
        result_text = tokenizer.decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        if len(generated) != streamer.count:
            raise RuntimeError("Generated token count mismatch")
        if result_text != "".join(streamer.pieces):
            raise RuntimeError("Streamed text does not match generated text")
        eos = cfg.eos_token_id
        eos_ids = {eos} if isinstance(eos, int) else set(eos or [])
        eos_seen = bool(generated and generated[-1] in eos_ids)
        metrics = streamer.metrics()
        selected = result_text.strip()
        valid = selected in task["choices"] and eos_seen
        emit({"type": "model_result", "model": key, "kind": "generation", "text": result_text,
              "task_sha256": task["task_sha256"], "label": selected if valid else None,
              "answer": task["choices"].get(selected) if valid else None, "valid_choice": valid,
              "input_tokens": input_tokens, "load_ms": round(load_ms, 3), **metrics,
              "latency_ms": round((time.perf_counter() - begin) * 1000, 3),
              "finish_reason": "eos" if eos_seen else "length"})

    def run(self, text, emit):
        begin = time.perf_counter()
        task = parse_task(text)
        emit({"type": "run_start", "order": list(MODEL_ORDER), "task": task})
        for key in MODEL_ORDER:
            emit({"type": "model_start", "model": key, "name": NAMES[key],
                  "kind": "classification" if key == "laya" else "generation"})
            try:
                load_ms = self.load(key, emit)
                emit({"type": "status", "model": key, "message": "분류 중…" if key == "laya" else "첫 토큰 생성 중…"})
                if key == "laya":
                    self.classify(task, load_ms, emit)
                else:
                    self.generate(key, task, load_ms, emit)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                raise
            except SharedTaskLimitError as exc:
                emit({"type": "error", "message": str(exc)})
                return
            except Exception as exc:
                emit({"type": "model_error", "model": key, "message": f"{type(exc).__name__}: {exc}"})
        emit({"type": "run_end", "elapsed_ms": round((time.perf_counter() - begin) * 1000, 3)})
