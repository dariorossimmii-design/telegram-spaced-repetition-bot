# telegram-spaced-repetition-bot
A Python Telegram bot for automated language learning using a custom spaced repetition system.
# Telegram Spaced Repetition Bot 🇵🇱

A Python-based Telegram bot designed to automate language learning through a custom spaced repetition system. Built to streamline the acquisition of Polish vocabulary, transitioning from a static local script to a dynamic, cloud-hosted conversational interface.

**Core Features**
* **Tiered Learning Progression:** Implements a multi-level mastery system. New words begin as Multiple Choice Questions (Level 0) and progress to strict typing exercises (Levels 1-3).
* **Automated Data Management:** Seamlessly reads from a structured CSV database and tracks user progress in an automatically generated JSON state file.
* **Continuous Entry Loop:** Features a built-in `/aggiungi` command that allows users to mass-import new vocabulary directly via Telegram, complete with real-time duplicate detection.
* **Typo Override:** Includes a manual override mechanism to forgive minor typing or diacritic errors without penalizing the learning progression.
* **Progress Reset:** Safely wipe current learning data using the `/reset` command with a built-in confirmation failsafe.
* **Cloud Ready:** Structured for continuous deployment on cloud platforms (e.g., PythonAnywhere) via infinite polling.

**Tech Stack**
* Python 3.x
* `pyTelegramBotAPI` (Telebot)
* JSON & CSV for lightweight data storage

**Database Setup**
The bot relies on a simple CSV file to load vocabulary. Populate `pl_vocabulary.csv` following the format `foreign_word,translation,lesson_number`. A basic template looks like this:

```csv
cześć,ciao,1
dziękuję,grazie,1
proszę,prego,1
