# AI Text Detector

A text detector built on a locally fine-tuned language model. Scores a sample
on a 0-100 "looks machine-generated" scale, with no cloud call.

## Why local
Most detectors phone home to an API, which is a problem when the text is
sensitive or you just want it to run on a laptop with no internet. This one
runs a small fine-tuned LM entirely on your machine.

## What it does
- Ingests a document or pasted text
- Runs it through the local model
- Returns a score + the tokens that drove it
- Batch mode for a folder of files

## The writeup
How it is built, what it gets right, and where it quietly fails, is covered in
the [PastAGI guide on building an AI text detector with local models](https://pastagi.com/guides/build-ai-text-detector-local-models/).

[More guides](https://pastagi.com/).
