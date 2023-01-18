import torch
import numpy as np
import pybullet as pyb
from gym import spaces
from typing import Union, List, Dict, TypedDict
from sensor.sensor import Sensor
import copy
from time import time
from abc import abstractmethod
from robot.ur5 import UR5
from .camera_utils import *
from .camera import CameraBase, CameraArgs

class StaticBodyCameraUR5(CameraBase):

    def __init__(self, robot : UR5, position_relative_to_effector: List = None, camera_args: CameraArgs = None, name : str = 'default_body_ur5', **kwargs):
        self.robot = robot
        self.relative_pos = position_relative_to_effector
        super().__init__(camera_args= camera_args, name= name, **kwargs)

    def _calculate_position(self):
        effector_position, effector_orientation = pyb.getLinkState(self.robot.object_id, self.robot.end_effector_link_id)[4:6]
        body_position, body_orientation = pyb.getLinkState(self.robot.object_id, self.robot.end_effector_link_id - 1)[4:6]
        effector_up_vector, effector_forward_vector, _ = directionalVectorsFromQuaternion(effector_orientation)
        self.camera_args['up_vector'] = effector_up_vector
        if self.relative_pos is None:
            target = add_list(effector_position, effector_forward_vector) # [p+v for p,v in zip(effector_position, effector_forward_vector)]
            body_forward_vector, body_up_vector, _ = directionalVectorsFromQuaternion(body_orientation)
            position = add_list(add_list(body_position, body_up_vector, 0.075), body_forward_vector, 0.075) # [p+u+f for p,u,f in zip(body_position, body_up_vector, body_forward_vector)]
        else:
            position = add_list(effector_position, self.relative_pos)
            target = add_list(position, effector_forward_vector)
        
        return position, target

    def _adapt_to_environment(self):
        self.pos, self.target = self._calculate_position()
        super()._adapt_to_environment()

class StaticFloatingCamera(CameraBase):
    """
    floating camera at position, if target is None, the camera will follow the robot's effector.
    """

    def __init__(self, robot : UR5, position: List, target: List = None, camera_args: CameraArgs = None, name : str = 'default_floating', **kwargs):
        super().__init__(target= target, camera_args= camera_args, name= name, **kwargs)
        self.robot = robot
        self.follow_effector = target is None
        self.pos = position

    def _adapt_to_environment(self):
        if self.follow_effector:
            self.target = pyb.getLinkState(self.robot.object_id, self.robot.end_effector_link_id)[4]
        super()._adapt_to_environment()
