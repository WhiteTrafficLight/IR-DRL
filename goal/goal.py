from abc import ABC, abstractmethod
from robot.robot import Robot
from typing import Tuple

class Goal(ABC):
    """
    Abstract Base Class for robot goals. Methods signed with abstractmethod need to be implemented by subclasses.
    See the position goal for examples.
    """

    def __init__(self, robot:Robot, normalize_rewards:bool, normalize_observations:bool, train:bool, max_steps:int, continue_after_success:bool=False, add_to_observation_space:bool=False):

        # each goal needs to have a robot assigned for which it is valid
        self.robot = robot

        # bool for training or evaluation, useful for when the goal has to change if it's in training
        self.train = train

        # the maximum steps which the env has to fulfill this goal
        self.max_steps = max_steps

        # wether the robot associated with this goal can continue to receive actions after the goal has been fulfilled (only relevant for multi robot setups)
        self.continue_after_success = continue_after_success

        # determines whether the rewards and observations given by this goal will be normalized
        self.normalize_rewards = normalize_rewards 
        self.normalize_observations = normalize_observations

        # this bool determines whether the goal will add an entry to the observation space
        # this is necessary for goals such as the position goal which will add relative position of its assigned robot's ee to the goal
        self.add_to_observation_space = add_to_observation_space

        # flags such that the automated processes elsewhere can recognize what this goal needs
        # set these yourself if they apply in a subclass
        self.needs_a_position = False  # goal needs a target position in the worldspace
        self.needs_a_rotation = False  # goal needs a target rotation in the worldspace

    @abstractmethod
    def get_observation_space_element(self) -> dict:
        """
        This method defines how the observation space element added by this goal will look.
        This method will only get called (and an element added to the observation space) if the add_to_observation_space bool is set to True.
        Return an empty dict if your goal does not need to add anything.
        """
        pass

    @abstractmethod
    def get_observation(self) -> dict:
        """
        Returns a dict with the data for the observation space element added by this goal, if any.
        This must return the data in the same format as defined below in the gym space.
        Also, if self.normalize is True the observations here should be normalized.
        """
        pass

    @abstractmethod
    def reward(self, step) -> Tuple[float, bool, bool, bool, bool]:
        """
        This method calculates the reward received by the assigned robot for this particular goal.
        Takes as input the current step count.
        The return value is a tuple of a float and four bools:
        - float: reward, should be normalized if self.normalize is True
        - bool #1: success signal
        - bool #2: done signal (episode over for all robots in env, not just this one)
        - bool #3: timeout signal (max steps condition violated, done signal must also be set to True)
        - bool #4: out of bounds signal (also set done to True)
        """
        pass

    @abstractmethod
    def on_env_reset(self):
        """
        This method will be called once the env resets itself and starts a new episode.
        This is usefull if you e.g. have some running metric that can change the goals parameters depending on training success.
        Doesn't have to do anything if not needed.
        """
        pass

    def build_visual_aux(self):
        """
        This method should add objects that are helpful to visualize the goal. In most cases this will be something 
        like marking the target zone. 
        """
        pass

    def get_data_for_logging(self) -> dict:
        """
        This method can be used to return goal-related data for logging.
        This could include stuff you return via get_observation, but also things like success rates etc.
        Passes an empty dict if not using this.
        """
        return {}