# LUNA Desktop — Build Requirements

This document records the non-negotiable requirements for the LUNA Desktop project.

## Product

LUNA is a local-first Windows desktop AI personal assistant and general-purpose computer-use agent. It should understand user goals, plan actions, use reusable desktop/browser tools, observe and verify results, run background tasks, speak through local Kokoro TTS, and maintain local SQLite memory.

## Architecture principles

- Build on the current repository; do not create a throwaway prototype.
- Keep the agent, planner, task manager, memory, automation, model manager, voice system, UI, and permissions modular.
- Prefer reusable computer-use tools over website-specific scripts.
- Never claim an action succeeded without verification.
- Keep user data and large model/voice assets outside Git.
- Do not use Firebase for local memory.
- API keys must never be committed to the repository.

## Local models

LUNA must support these exact Kokoro ONNX model files:

- `model_q8f16.onnx` — preferred/default
- `model_fp16.onnx` — supported alternative

The application should provide a model/voice import and selection workflow. Do not require large model files to be stored in Git.

## Voice

Use local Kokoro TTS. Voice assets may be imported separately from the application. Provide voice selection and a real test-voice function.

## Automation

The system should be general-purpose and capable of combining browser and desktop tools, including accessibility information, keyboard/mouse input, scrolling, screenshots, window management, application launching, clipboard, filesystem operations, and controlled terminal operations.

Important external actions such as sending messages, deleting important files, purchases, or major system changes should have an approval checkpoint by default.

## Memory

Use local SQLite under the user's LUNA home directory. Provide controls to view, search, delete, clear, and disable memory.

## Background operation

LUNA should continue running when its main UI is minimized. Long-running tasks need persistent states such as queued, running, paused, waiting-for-user, completed, failed, and cancelled.

## Personality

Settings should provide at least:

- Professional Assistant
- Friendly Assistant
- Friendly Companion
- Concise
- Custom

Friendly Companion should be warm and supportive while remaining an assistant.

## Build

Use GitHub Actions to test and package a Windows executable. Large AI/TTS assets must remain outside Git and be imported by the user separately.

## Quality rule

Do not leave fake implementations, decorative controls, or silently failing subsystems. If a required component is incomplete, diagnose it, implement it, test it, and fix failures before declaring it complete.
