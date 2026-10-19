# Third-party components

Built with Llama

- **Laya** model and library: Convai Innovations / NandhaKishorM, Apache License 2.0. Source: https://github.com/NandhaKishorM/laya ; model: https://huggingface.co/convaiinnovations/laya . The pinned upstream model card and configurations are downloaded with the model files, not vendored as application code.
- **Llama 3.2 Instruct 1B and 3B**: Meta, under the Llama 3.2 Community License and its Acceptable Use Policy. See LICENSES/LICENSE_LLAMA_3_2.txt and LICENSES/NOTICE_Llama.txt. Public model files are downloaded from the pinned Unsloth distributions; the original weights are not committed to this repository. Model sources: https://huggingface.co/unsloth/Llama-3.2-1B-Instruct and https://huggingface.co/unsloth/Llama-3.2-3B-Instruct .
- **PyTorch**, **Transformers**, and the remaining installed dependencies retain their upstream licenses. The installer obtains their published distributions; this repository does not vendor their source trees.

The application is an independent local comparison demo. It does not use TypeSafe Jev's service, model weights, or private architecture.
