from abc import ABC, abstractmethod
import numpy as np

class Robot(ABC):

    # testing, change later
    def __init__(self):
        super().__init__()
        self.joints_ids = [1,2,3,4,5]
        self.name = "ur5_1"
        self.joints_limits_lower = np.array([0,0,0,0,0])
        self.joints_limits_upper = np.array([np.pi, np.pi, np.pi, np.pi, np.pi])
        self.joints_range = self.joints_limits_upper - self.joints_limits_lower
        self.id = 0