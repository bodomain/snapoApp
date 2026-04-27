import time
import argparse
import subprocess
import shutil
import database
import sys
import select
import termios
import tty
import plot


def play_sound():
    """Plays a notification sound using system tools."""
    sound_file = "bell.wav"
    try:
        # Check for available players
        if shutil.which("aplay"):
            subprocess.run(["aplay", "-q", sound_file], check=False)
        elif shutil.which("paplay"):
            subprocess.run(["paplay", sound_file], check=False)
        elif shutil.which("ffplay"):
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", sound_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            # Fallback to terminal bell
            print("\a", end="", flush=True)
    except Exception:
        # Fallback to terminal bell
        print("\a", end="", flush=True) 


def countdown(t, label, activity_name=None, comment="", endless=False):
    """Displays a countdown timer with pause and exit functionality."""
    if endless:
        print(f"{label}: Starting endless session... (p:pause, l:log&exit, q:quit)", end="\r")
    else:
        print(f"{label}: Starting... (p:pause, l:log&exit, q:quit)", end="\r")

    initial_t = t
    # Save original terminal settings
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())

        elapsed_seconds = 0
        while endless or t > 0:
            if not endless:
                mins, secs = divmod(t, 60)
                remaining_timer = "{:02d}:{:02d}".format(mins, secs)
                elapsed = initial_t - t
            else:
                remaining_timer = "Endless"
                elapsed = elapsed_seconds

            e_mins, e_secs = divmod(elapsed, 60)
            elapsed_timer = "{:02d}:{:02d}".format(e_mins, e_secs)

            print(
                f"{label}: time: {elapsed_timer}    remaining: {remaining_timer}          ",
                end="\r",
            )

            # Wait for input or timeout (1 second)
            rlist, _, _ = select.select([sys.stdin], [], [], 1)

            if rlist:
                key = sys.stdin.read(1)
                if key.lower() == "p":
                    print(f"\r{label}: PAUSED (p:resume, q:quit)   ", end="")
                    while True:
                        # Wait indefinitely for input when paused
                        rlist_paused, _, _ = select.select([sys.stdin], [], [])
                        if rlist_paused:
                            key_paused = sys.stdin.read(1)
                            if key_paused.lower() == "p":
                                print(
                                    f"\r{label}: Resuming...                  ", end=""
                                )
                                break
                            elif key_paused.lower() == "q":
                                key = "q"
                                break
                            elif key_paused.lower() == "l":
                                # Handle exit from pause state
                                key = "l"
                                break

                if key.lower() == "l":
                    total_elapsed = elapsed_seconds if endless else (initial_t - t)
                    elapsed_minutes = total_elapsed / 60
                    print(f"\nExiting... Session logged: {elapsed_minutes:.2f} min")
                    if activity_name:
                        database.log_session(activity_name, elapsed_minutes, comment)
                    sys.exit(0)

                if key.lower() == "q":
                    print("\nQuitting without logging...")
                    sys.exit(0)

            else:
                # Timeout reached, decrement/increment timer
                if endless:
                    elapsed_seconds += 1
                else:
                    t -= 1
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print()  # Ensure newline after loop


def start_prodz(work_minutes, break_minutes, long_break_minutes, cycles, activity, comment=""):
    """Starts the prodzCLI timer."""
    database.init_db()
    for i in range(cycles):
        print(f"--- Cycle {i + 1}/{cycles} ---")
        print(f"Starting work session: {activity}")
        countdown(work_minutes * 60, "Work", activity, comment)
        print("\nWork session complete!")
        play_sound()
        database.log_session(activity, work_minutes, comment)

        if (i + 1) % 4 == 0:
            print("Starting long break...")
            countdown(long_break_minutes * 60, "Long Break")
            print("\nLong break complete!")
            play_sound()
        else:
            print("Starting short break...")
            countdown(break_minutes * 60, "Break")
            print("\nBreak complete!")
            play_sound()

    print("prodzCLI session finished!")


def start_endless(activity, comment=""):
    """Starts an endless prodzCLI session."""
    database.init_db()
    print(f"--- Endless Session ---")
    print(f"Starting work session: {activity}")
    countdown(0, "Work", activity, comment, endless=True)


def input_safe_int(prompt, default):
    try:
        val = input(f"{prompt} [{default}]: ").strip()
        return int(val) if val else default
    except ValueError:
        return default


def show_menu():
    while True:
        print("\n--- Prodz CLI Menu ---")
        print("1. Start Default Session (25/5)")
        print("2. Start Custom Session")
        print("3. Start Endless Session")
        print("4. View Statistics")
        print("5. Quit")

        choice = input("Enter choice: ").strip()

        if choice == "1":
            activity = input("Activity name [default]: ").strip() or "default"
            comment = input("Comment [optional]: ").strip()
            start_prodz(25, 5, 15, 4, activity, comment)
        elif choice == "2":
            activity = input("Activity name [custom]: ").strip() or "custom"
            comment = input("Comment [optional]: ").strip()
            w = input_safe_int("Work minutes", 25)
            b = input_safe_int("Short break minutes", 5)
            lb = input_safe_int("Long break minutes", 15)
            c = input_safe_int("Cycles", 4)
            start_prodz(w, b, lb, c, activity, comment)
        elif choice == "3":
            activity = input("Activity name [endless]: ").strip() or "endless"
            comment = input("Comment [optional]: ").strip()
            start_endless(activity, comment)
        elif choice == "4":
            try:
                data = plot.get_data()
                plot.draw_chart(data)
            except Exception as e:
                print(f"Error showing stats: {e}")
        elif choice == "5":
            print("Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice, try again.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(
            description="prodzCLI - A simple productivity timer."
        )
        parser.add_argument(
            "-w",
            "--work",
            type=int,
            default=25,
            help="Work session duration in minutes (default: 25)",
        )
        parser.add_argument(
            "-b",
            "--break",
            type=int,
            default=2,
            help="Short break duration in minutes (default: 5)",
        )
        parser.add_argument(
            "-lb",
            "--long-break",
            type=int,
            default=6,
            help="Long break duration in minutes (default: 15)",
        )
        parser.add_argument(
            "-c",
            "--cycles",
            type=int,
            default=4,
            help="Number of work cycles (default: 4)",
        )
        parser.add_argument(
            "-a",
            "--activity",
            type=str,
            default="whatever",
            help="Name of the activity (default: 'whatever')",
        )
        parser.add_argument(
            "-t",
            "--text",
            type=str,
            default="",
            help="Short comment about the activity",
        )
        parser.add_argument(
            "-e",
            "--endless",
            action="store_true",
            help="Start an endless session",
        )
        args = parser.parse_args()

        if args.endless:
            start_endless(args.activity, args.text)
        else:
            start_prodz(
                args.work,
                getattr(args, "break"),
                args.long_break,
                args.cycles,
                args.activity,
                args.text,
            )
    else:
        show_menu()
