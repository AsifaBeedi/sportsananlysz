class TimingAnalyzer:
    def analyze(self, frame_index, ball_position, racket_position):
        if not ball_position or not racket_position:
            return {}

        dx = ball_position[0] - racket_position[0]
        dy = ball_position[1] - racket_position[1]

        distance = (dx**2 + dy**2) ** 0.5

        contact = distance < 30

        timing = "Perfect" if distance < 20 else ("Early" if dx < 0 else "Late")

        return {
            "frame": frame_index,
            "distance": float(distance),
            "contact": contact,
            "timing": timing
        }