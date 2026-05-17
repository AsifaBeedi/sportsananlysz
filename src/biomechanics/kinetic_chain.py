import numpy as np


class KineticChainAnalyzer:
    def analyze(self, joints):
        hip = joints.get("hip")
        shoulder = joints.get("shoulder")
        knee = joints.get("knee")

        if hip is None or shoulder is None or knee is None:
            return {}

        hip_drive = np.linalg.norm(np.array(hip) - np.array(knee))
        shoulder_drive = np.linalg.norm(np.array(shoulder) - np.array(hip))

        efficiency = (hip_drive + shoulder_drive) / 2

        status = "Efficient" if efficiency > 40 else "Weak Chain"

        return {
            "hip_drive": float(hip_drive),
            "shoulder_drive": float(shoulder_drive),
            "efficiency": float(efficiency),
            "status": status
        }
