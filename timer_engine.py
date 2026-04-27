from dataclasses import dataclass


@dataclass
class TimerConfig:
    work_minutes: int = 25
    break_minutes: int = 5
    long_break_minutes: int = 15
    cycles: int = 4
    activity: str = "default"
    comment: str = ""
    endless: bool = False


class SessionTimer:
    def __init__(self):
        self.config = TimerConfig()
        self.phase = "idle"
        self.cycle_index = 0
        self.remaining_seconds = 0
        self.elapsed_work_seconds = 0
        self.phase_elapsed_seconds = 0
        self.running = False
        self.paused = False
        self.completed = False

    def start(self, config):
        self.config = config
        self.cycle_index = 1
        self.elapsed_work_seconds = 0
        self.completed = False
        self.paused = False
        self.running = True
        self.phase = "work"
        self.phase_elapsed_seconds = 0
        self.remaining_seconds = 0 if config.endless else config.work_minutes * 60

    def pause(self):
        if self.running:
            self.paused = True

    def resume(self):
        if self.running:
            self.paused = False

    def stop(self):
        self.running = False
        self.paused = False
        self.phase = "idle"

    def tick(self):
        if not self.running or self.paused or self.completed:
            return None

        self.phase_elapsed_seconds += 1
        if self.phase == "work":
            self.elapsed_work_seconds += 1

        if self.config.endless:
            return None

        self.remaining_seconds = max(0, self.remaining_seconds - 1)
        if self.remaining_seconds > 0:
            return None

        return self._advance_phase()

    def _advance_phase(self):
        finished_phase = self.phase
        if self.phase == "work":
            if self.cycle_index >= self.config.cycles:
                self.completed = True
                self.running = False
                self.phase = "complete"
                return {"finished": finished_phase, "next": "complete"}

            self.phase = "long_break" if self.cycle_index % 4 == 0 else "break"
            minutes = (
                self.config.long_break_minutes
                if self.phase == "long_break"
                else self.config.break_minutes
            )
            self.remaining_seconds = minutes * 60
        else:
            self.cycle_index += 1
            self.phase = "work"
            self.remaining_seconds = self.config.work_minutes * 60

        self.phase_elapsed_seconds = 0
        return {"finished": finished_phase, "next": self.phase}

    def elapsed_minutes(self):
        return self.elapsed_work_seconds / 60

    def display_seconds(self):
        if self.config.endless or self.phase == "work" and self.config.endless:
            return self.elapsed_work_seconds
        return self.remaining_seconds


def format_seconds(seconds):
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
