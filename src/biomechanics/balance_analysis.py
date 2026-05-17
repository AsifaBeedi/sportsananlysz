import numpy as np

class BalanceAnalyzer:
    def analyze(self, joints):
        hip = joints.get("hip")
        left_foot = joints.get("left_foot")
        right_foot = joints.get("right_foot")

        if hip is None or left_foot is None or right_foot is None:
            return {}

        center = np.array(hip)
        base = (np.array(left_foot) + np.array(right_foot)) / 2

        stability = np.linalg.norm(center - base)
        balanced = bool(stability < 40)

        return {
            "stability": float(stability),
            "balanced": balanced,
            "status": "stable" if balanced else "unstable",
        }
