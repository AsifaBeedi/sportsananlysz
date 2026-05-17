class ContactAnalyzer:
    def analyze(self, ball_bbox, racket_bbox):
        if ball_bbox is None or racket_bbox is None:
            return {}

        bx, by, _, _ = ball_bbox
        rx, ry, _, _ = racket_bbox

        dx = abs(bx - rx)
        dy = abs(by - ry)

        overlap = dx < 30 and dy < 30

        quality = "Good Contact" if overlap else "Missed"

        return {
            "contact": overlap,
            "quality": quality,
            "distance": float((dx**2 + dy**2) ** 0.5)
        }
