import sqlite3
import shutil

import database

DB_NAME = "prodz.db"

# ANSI Colors for terminal output
COLORS = [
    "\033[31m", # Red
    "\033[32m", # Green
    "\033[33m", # Yellow
    "\033[34m", # Blue
    "\033[35m", # Magenta
    "\033[36m", # Cyan
    "\033[91m", # Light Red
    "\033[92m", # Light Green
    "\033[93m", # Light Yellow
    "\033[94m", # Light Blue
    "\033[95m", # Light Magenta
    "\033[96m", # Light Cyan
]
RESET = "\033[0m"
DIM = "\033[2m"

def get_data():
    database.init_db(sync_enabled=False)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT date, activity, duration_minutes
        FROM sessions
        ORDER BY date ASC, timestamp ASC
    """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def summarize_daily(data):
    daily_stats = {}
    activities = set()

    for date, activity, duration in data:
        if date not in daily_stats:
            daily_stats[date] = {}
        if activity not in daily_stats[date]:
            daily_stats[date][activity] = []
        daily_stats[date][activity].append(float(duration))
        activities.add(activity)

    days = []
    for date, acts in daily_stats.items():
        total = sum(sum(durations) for durations in acts.values())
        days.append({"date": date, "activities": acts, "total": total})

    return {
        "days": days,
        "activities": sorted(activities),
        "max_total": max((day["total"] for day in days), default=0),
    }

def draw_chart(data):
    if not data:
        print("No data found in database.")
        return

    summary = summarize_daily(data)
    daily_stats = {day["date"]: day["activities"] for day in summary["days"]}

    # Assign colors to activities
    sorted_activities = summary["activities"]
    activity_colors = {act: COLORS[i % len(COLORS)] for i, act in enumerate(sorted_activities)}

    # Calculate max daily total for scaling
    max_val = summary["max_total"]

    if max_val == 0:
        return

    # Terminal dimensions
    cols, _ = shutil.get_terminal_size((80, 20))
    max_label_len = max(len(d) for d in daily_stats.keys())
    # Available width (date + separator + space + total text + extra buffer)
    bar_width = cols - max_label_len - 15 

    print("\nDaily Activity (Duration in Minutes)\n")

    for date, acts in daily_stats.items():
        total_duration = sum(sum(durations) for durations in acts.values())
        
        # Build the stacked bar
        bar_str = ""
        
        for activity in sorted_activities:
            if activity in acts:
                durations = acts[activity]
                color = activity_colors[activity]
                
                # Build segments for this activity
                segments = []
                for dur in durations:
                    if dur > 0:
                        # Calculate length for this specific session
                        segment_len = int((dur / max_val) * bar_width)
                        # Ensure visibility for small sessions
                        if segment_len == 0 and dur > 0:
                            segment_len = 1
                        segments.append("█" * segment_len)
                
                # Join sessions with a thin separator
                # We apply the color to the blocks, and use a dim separator
                activity_bar = f"{RESET}{DIM}|{RESET}{color}".join(segments)
                
                bar_str += f"{color}{activity_bar}{RESET}"
        
        print(f"{date} | {bar_str} {total_duration:.2f}m")

    # Legend
    print("\nLegend:")
    for activity in sorted_activities:
        print(f"{activity_colors[activity]}█ {activity}{RESET}", end="  ")
    print("\n")

if __name__ == "__main__":
    try:
        data = get_data()
        draw_chart(data)
    except sqlite3.OperationalError:
        print("Database not found or empty. Run a prodzCLI session first.")
