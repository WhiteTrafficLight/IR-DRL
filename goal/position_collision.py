from goal.goal import Goal
import numpy as np
from robot.robot import Robot
from gym.spaces import Box
import pybullet as pyb

class PositionCollisionGoal(Goal):
    """
    This class implements a goal of reaching a certain position while avoiding collisions.
    The reward function follows Yifan's code.
    """

    def __init__(self, robot: Robot, 
                       normalize_rewards: bool, 
                       normalize_observations: bool,
                       train: bool,
                       max_steps: int, 
                       reward_success=10, 
                       reward_collision=-10,
                       reward_distance_mult=-0.01,
                       dist_threshold_start=3e-1,
                       dist_threshold_end=1e-2,
                       dist_threshold_increment_start=1e-2,
                       dist_threshold_increment_end=1e-3):
        super().__init__(robot, train, max_steps, normalize_rewards, True, normalize_observations)  # True for adding to observation space

        # set output name for observation space
        self.output_name = "PositionGoal_" + self.robot.name

        # set the flags
        self.needs_a_position = True
        self.needs_a_rotation = False

        # set the reward that's given if the ee reaches the goal position and for collision
        self.reward_success = reward_success
        self.reward_collision = reward_collision
        
        # multiplicator for the distance reward
        self.reward_distance_mult = reward_distance_mult

        # set the distance thresholds and the increments for changing them
        self.distance_threshold = dist_threshold_start if self.train else dist_threshold_end
        self.distance_threshold_start = dist_threshold_increment_start
        self.distance_threshold_end = dist_threshold_end
        self.distance_threshold_increment_start = dist_threshold_increment_start
        self.distance_threshold_increment_end = dist_threshold_increment_end

        # set up normalizing constants for faster normalizing
        #     reward
        self.normalizing_constant_a_reward = 2 / (self.reward_success - reward_collision)
        self.normalizing_constant_b_reward = 1 - self.normalizing_constant_a_reward * self.reward_success
        #     observation
        #       get maximum ranges from world associated with robot
        vec_distance_max = np.array([self.robot.world.x_max - self.robot.world.x_min, self.robot.world.y_max - self.robot.world.y_min, self.robot.world.z_max - self.robot.world.z_min])
        vec_distance_min = -1 * vec_distance_max
        distance_max = np.linalg.norm(vec_distance_max)
        #       constants
        self.normalizing_constant_a_obs = np.zeros(4)  # 3 for difference vector and 1 for distance itself
        self.normalizing_constant_b_obs = np.zeros(4)  # 3 for difference vector and 1 for distance itself
        self.normalizing_constant_a_obs[:3] = 2 / (vec_distance_max - vec_distance_min)
        self.normalizing_constant_a_obs[3] = 1 / distance_max  # distance only between 0 and 1
        self.normalizing_constant_b_obs[:3] = np.ones(3) - np.multiply(self.normalizing_constant_a_obs[:3], vec_distance_max)
        self.normalizing_constant_b_obs[3] = 1 - self.normalizing_constant_a_obs[3] * distance_max  # this is 0, but keeping it in the code for symmetry

        # placeholders so that we have access in other methods without doing double work
        self.distance = None
        self.position = None
        self.reward_value = 0
        self.shaking = 0
        self.collided = False
        self.timeout = False
        self.out_of_bounds = False
        self.is_success = False
        self.done = False
        self.past_distances = []

        # statistics 
        self.stat_buffer_size = 25  # in episodes
        self.stat_success = []
        self.stat_timeout = []
        self.stat_shaking = []
        self.stat_collision = []
        self.stat_reward = []
        self.stat_oob = []
        self.stat_distance = []  # same as past_distances, but keeping it this way for symmetry

    def get_observation_space_element(self) -> dict:
        if self.add_to_observation_space:
            ret = dict()
            if self.normalize_observations:
                ret[self.output_name ] = Box(low=-1, high=1, shape=(4,), dtype=np.float32)
            else:
                high = np.array([self.robot.world.x_max - self.robot.world.x_min, self.robot.world.y_max - self.robot.world.y_min, self.robot.world.z_max - self.robot.world.z_min, 1])
                low = np.array([-self.robot.world.x_max + self.robot.world.x_min, -self.robot.world.y_max + self.robot.world.y_min, -self.robot.world.z_max + self.robot.world.z_min, 0])
                ret[self.output_name ] = Box(low=low, high=high, shape=(4,), dtype=np.float32)

            return ret
        else:
            return {}

    def get_observation(self) -> dict:
        # get the data
        self.position = self.robot.position_rotation_sensor.position
        self.target = self.robot.world.position_targets[self.robot.id]
        dif = self.target - self.position
        self.distance = np.linalg.norm(dif)

        self.past_distances.append(self.distance)
        if len(self.past_distances) > 10:
            self.past_distances.pop(0)

        ret = np.zeros(4)
        ret[:3] = dif
        ret[3] = self.distance
        
        if self.normalize_observations:
            return {self.output_name: np.multiply(self.normalizing_constant_a_obs, ret) + self.normalizing_constant_b_obs} 
        else:
            return {self.output_name: ret}

    def reward(self, step):

        reward = 0

        self.out_of_bounds = self._out()
        self.collided = self.robot.world.collision

        shaking = 0
        if len(self.past_distances) >= 10:
            arrow = []
            for i in range(0,9):
                arrow.append(0) if self.past_distances[i + 1] - self.past_distances[i] >= 0 else arrow.append(1)
            for j in range(0,8):
                if arrow[j] != arrow[j+1]:
                    shaking += 1
        self.shaking = shaking
        reward -= shaking * 0.005

        self.is_success = False
        if self.out_of_bounds:
            self.done = True
            reward += self.reward_collision / 2
        elif self.collided:
            self.done = True
            reward += self.reward_collision
        elif self.distance < self.distance_threshold:
            self.done = True
            self.is_success = True
            reward += self.reward_success
        elif step > self.max_steps:
            self.done = True
            self.timeout = True
            reward += self.reward_collision / 10
        else:
            self.done = False
            reward += self.reward_distance_mult * self.distance
        
        self.reward_value = reward
        if self.normalize_rewards:
            self.reward_value = self.normalizing_constant_a_reward * self.reward_value + self.normalizing_constant_b_reward

        # update the stats at the end of an episode
        if self.done:
            self.stat_success.append(self.is_success)
            if len(self.stat_success) > self.stat_buffer_size:
                self.stat_success.pop(0)

            self.stat_oob.append(self.out_of_bounds)
            if len(self.stat_oob) > self.stat_buffer_size:
                self.stat_oob.pop(0)

            self.stat_collision.append(self.collided)
            if len(self.stat_collision) > self.stat_buffer_size:
                self.stat_collision.pop(0)

            self.stat_timeout.append(self.collided)
            if len(self.stat_timeout) > self.stat_buffer_size:
                self.stat_timeout.pop(0)

            self.stat_shaking.append(self.shaking)
            if len(self.stat_shaking) > self.stat_buffer_size:
                self.stat_shaking.pop(0)

            self.stat_reward.append(self.reward_value)
            if len(self.stat_reward) > self.stat_buffer_size:
                self.stat_reward.pop(0)

            self.stat_distance.append(self.distance)
            if len(self.stat_distance) > self.stat_buffer_size:
                self.stat_distance.pop(0)
        
        # return
        return self.reward_value, self.is_success, self.done    

    def on_env_reset(self):
        
        self.timeout = False
        self.is_success = False
        self.is_done = False
        self.collided = False
        self.out_of_bounds = False
        
        # set the distance threshold according to the success of the training
        if self.train: 
            success_rate = np.average(self.stat_success)

            # calculate increment
            ratio_start_end = (self.distance_threshold - self.distance_threshold_increment_end) / (self.distance_threshold_increment_start - self.distance_threshold_increment_end)
            increment = (self.distance_threshold_increment_start - self.distance_threshold_increment_end) * ratio_start_end + self.distance_threshold_increment_end
            if success_rate > 0.8 and self.distance_threshold > self.distance_threshold_end:
                self.distance_threshold -= increment
            elif success_rate < 0.8 and self.distance_threshold < self.distance_threshold_start:
                self.distance_threshold += increment / 5  # upwards movement should be slower
            if self.distance_threshold > self.distance_threshold_start:
                self.distance_threshold = self.distance_threshold_start
            if self.distance_threshold < self.distance_threshold_end:
                self.distance_threshold = self.distance_threshold_end

    def build_visual_aux(self):
        # build a sphere of distance_threshold size around the target
        self.target = self.robot.world.position_targets[self.robot.id]
        pyb.createMultiBody(baseMass=0,
                            baseVisualShapeIndex=pyb.createVisualShape(shapeType=pyb.GEOM_SPHERE, radius=self.distance_threshold, rgbaColor=[0, 1, 0, 1]),
                            basePosition=self.target)

    def get_data_for_logging(self) -> dict:
        logging_dict = dict()

        logging_dict["success_rate" + self.robot.name + "_" + str(self.robot.id)] = np.average(self.stat_success)
        logging_dict["timeout_rate" + self.robot.name + "_" + str(self.robot.id)] = np.average(self.stat_timeout)
        logging_dict["outofbounds_rate" + self.robot.name + "_" + str(self.robot.id)] = np.average(self.stat_oob)
        logging_dict["collision_rate" + self.robot.name + "_" + str(self.robot.id)] = np.average(self.stat_collision)
        logging_dict["shaking_" + self.robot.name + "_" + str(self.robot.id)] = np.average(self.stat_shaking)
        logging_dict["reward_" + self.robot.name + "_" + str(self.robot.id)] = np.average(self.stat_reward)
        logging_dict["distance_" + self.robot.name + "_" + str(self.robot.id)] = np.average(self.stat_distance)

        return logging_dict

    ###################
    # utility methods #
    ###################

    def _out(self):
        
        x, y, z = self.position
        if x > self.robot.world.x_max or x < self.robot.world.x_min:
            return True
        elif y > self.robot.world.y_max or y < self.robot.world.y_min:
            return True
        elif z > self.robot.world.z_max or z < self.robot.world.z_min:
            return True
        return False