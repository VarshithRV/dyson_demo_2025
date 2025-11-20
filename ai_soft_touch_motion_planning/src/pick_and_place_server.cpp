// pick and place server

#include <memory>
#include <functional>
#include <string>
#include <chrono>
#include <cstdlib>
#include <thread>

#include "moveit/move_group_interface/move_group_interface.h"
#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/pose.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "example_interfaces/srv/trigger.hpp"
#include "ai_soft_touch_motion_planning_msgs/srv/pick.hpp"

using namespace std::chrono_literals;
using moveit::planning_interface::MoveGroupInterface;


class PickPlace{
    public: 
        PickPlace(rclcpp::Node::SharedPtr &node){
            node_ = node;
            
            node_->declare_parameter<std::string>("planning_group", "right_ur16e");
            
            node_->declare_parameter<double>("place_x", 0.0);
            node_->declare_parameter<double>("place_y", 0.0);
            node_->declare_parameter<double>("place_z", 0.0);
            
            node_->declare_parameter<double>("orientation_w", 1.0);
            node_->declare_parameter<double>("orientation_x", 0.0);
            node_->declare_parameter<double>("orientation_y", 0.0);
            node_->declare_parameter<double>("orientation_z", 0.0);

            node_->declare_parameter<double>("pick_offset_x", 0.0);
            node_->declare_parameter<double>("pick_offset_y", 0.0);
            node_->declare_parameter<double>("pick_offset_z", 0.0);

            node_->declare_parameter<double>("look_offset_x", 0.0);
            node_->declare_parameter<double>("look_offset_y", 0.0);
            node_->declare_parameter<double>("look_offset_z", 0.0);
            
            node_->declare_parameter<double>("height_of_movement", 0.25);

            planning_group_ = node_->get_parameter("planning_group").as_string();
            
            orientation_.push_back(node->get_parameter("orientation_w").as_double());
            orientation_.push_back(node->get_parameter("orientation_x").as_double());
            orientation_.push_back(node->get_parameter("orientation_y").as_double());
            orientation_.push_back(node->get_parameter("orientation_z").as_double());

            place_position_.push_back(node->get_parameter("place_x").as_double());
            place_position_.push_back(node->get_parameter("place_y").as_double());
            place_position_.push_back(node->get_parameter("place_z").as_double());

            pick_offset_.push_back(node->get_parameter("pick_offset_x").as_double());
            pick_offset_.push_back(node->get_parameter("pick_offset_y").as_double());
            pick_offset_.push_back(node->get_parameter("pick_offset_z").as_double());

            look_offset_.push_back(node->get_parameter("look_offset_x").as_double());
            look_offset_.push_back(node->get_parameter("look_offset_y").as_double());
            look_offset_.push_back(node->get_parameter("look_offset_z").as_double());

            height_of_movement_=node->get_parameter("height_of_movement").as_double();

            move_group_interface_ = std::make_shared<moveit::planning_interface::MoveGroupInterface>(node, planning_group_);
            
            bool ok = move_group_interface_->startStateMonitor(5.0);
            if (!ok)
                RCLCPP_WARN(node_->get_logger(), "State monitor did not receive joint states within 5 seconds");
            
            auto planning_frame = this->move_group_interface_->getPlanningFrame();
            RCLCPP_INFO(node->get_logger(),"Planning frame : %s",planning_frame.c_str());
            
            print_state_server_= node_->create_service<example_interfaces::srv::Trigger>("~/print_robot_state",std::bind(&PickPlace::print_state,this,std::placeholders::_1,std::placeholders::_2));
            pick_and_place_server_ = node_->create_service<ai_soft_touch_motion_planning_msgs::srv::Pick>("~/pick_and_place",std::bind(&PickPlace::pick_and_place_server,this,std::placeholders::_1,std::placeholders::_2));

        }

        void move_to_pose(const geometry_msgs::msg::Pose &pose){
            move_group_interface_->setPoseTarget(pose);
            auto const [success, plan] = [this]{
                moveit::planning_interface::MoveGroupInterface::Plan msg;
                auto const ok=static_cast<bool>(this->move_group_interface_->plan(msg));
                return std::make_pair(ok,msg);
            }();
            if(success)
                move_group_interface_->execute(plan);
            else
                RCLCPP_ERROR(node_->get_logger(),"Planning Failed");
            move_group_interface_->clearPoseTargets();
        }

        bool move_to_pose_cartesian(const geometry_msgs::msg::Pose &pose){
            std::vector<geometry_msgs::msg::Pose> waypoints;
            waypoints.push_back(move_group_interface_->getCurrentPose().pose);
            waypoints.push_back(pose);

            moveit_msgs::msg::RobotTrajectory trajectory;
            const double eef_step = 0.01;
            const double jump_threshold = 0.0;

            double fraction = move_group_interface_->computeCartesianPath(
                waypoints, eef_step, jump_threshold, trajectory);
            
            if (fraction < 1.0) {
                RCLCPP_ERROR(node_->get_logger(), "Cartesian path planning failed, fraction: %f", fraction);
                return false;
            }
        
            moveit::planning_interface::MoveGroupInterface::Plan plan;
            plan.trajectory_ = trajectory;
        
            auto result = move_group_interface_->execute(plan);
            if (result != moveit::core::MoveItErrorCode::SUCCESS) {
                RCLCPP_ERROR(node_->get_logger(), "Cartesian path execution failed");
                return false;
            }
            return true;
        }

        void pick_and_place_server(const ai_soft_touch_motion_planning_msgs::srv::Pick_Request::SharedPtr request,ai_soft_touch_motion_planning_msgs::srv::Pick_Response::SharedPtr response){
            geometry_msgs::msg::Pose approx_pick;
            approx_pick.position = request->object_position;
            approx_pick.position.x += pick_offset_[0];
            approx_pick.position.y += pick_offset_[1];
            approx_pick.position.z += pick_offset_[2];
            approx_pick.orientation.w = orientation_[0];
            approx_pick.orientation.x = orientation_[1];
            approx_pick.orientation.y = orientation_[2];
            approx_pick.orientation.z = orientation_[3];

            auto current_pose = this->move_group_interface_->getCurrentPose().pose;

            geometry_msgs::msg::Pose place;
            place.position.x = place_position_[0];
            place.position.y = place_position_[1];
            place.position.z = place_position_[2];
            place.orientation.w = orientation_[0];
            place.orientation.x = orientation_[1];
            place.orientation.y = orientation_[2];
            place.orientation.z = orientation_[3];

            geometry_msgs::msg::Pose target;

            target = current_pose;
            target.position.z = height_of_movement_;
            if (!move_to_pose_cartesian(target)) {
                response->result = false;
                return;
            }

            geometry_msgs::msg::Pose look_pose = approx_pick;
            look_pose.position.x += look_offset_[0];
            look_pose.position.y += look_offset_[1];
            look_pose.position.z += look_offset_[2];
            if (!move_to_pose_cartesian(look_pose)) {
                response->result = false;
                return;
            }

            // at this place, do perception again and get the pick position and substitute instead of approx_pick

            if (!move_to_pose_cartesian(approx_pick)) {
                response->result = false;
                return;
            }

            geometry_msgs::msg::Pose post_pick = approx_pick;
            post_pick.position.z = height_of_movement_;
            if (!move_to_pose_cartesian(post_pick)) {
                response->result = false;
                return;
            }

            geometry_msgs::msg::Pose pre_place = place;
            pre_place.position.z = height_of_movement_;
            if (!move_to_pose_cartesian(pre_place)) {
                response->result = false;
                return;
            }

            if (!move_to_pose_cartesian(place)) {
                response->result = false;
                return;
            }

            if (!move_to_pose_cartesian(pre_place)) {
                response->result = false;
                return;
            }
            response->result = true;
        }


        void print_state(const example_interfaces::srv::Trigger_Request::SharedPtr request, example_interfaces::srv::Trigger_Response::SharedPtr response){ // not working, stupid timer issue
            auto current_state = move_group_interface_->getCurrentState();
            auto current_pose = move_group_interface_->getCurrentPose();
            auto current_joint_values = move_group_interface_->getCurrentJointValues();
            auto print_pose = [this,current_state, current_joint_values, current_pose](){
                double x = current_pose.pose.position.x;
                double y = current_pose.pose.position.y;
                double z = current_pose.pose.position.z;
                double qx = current_pose.pose.orientation.x;
                double qy = current_pose.pose.orientation.y;
                double qz = current_pose.pose.orientation.z;
                double qw = current_pose.pose.orientation.w;
                RCLCPP_INFO(this->node_->get_logger(),"X : %f",x);
                RCLCPP_INFO(this->node_->get_logger(),"Y : %f",y);
                RCLCPP_INFO(this->node_->get_logger(),"Z : %f",z);
                RCLCPP_INFO(this->node_->get_logger(),"Qx : %f",qx);
                RCLCPP_INFO(this->node_->get_logger(),"Qy : %f",qy);
                RCLCPP_INFO(this->node_->get_logger(),"Qz : %f",qz);
                RCLCPP_INFO(this->node_->get_logger(),"Qw : %f",qw);
                std::string message;
                for(std::size_t i=0; i<current_joint_values.size(); i++)
                    message = "Joint " + std::to_string(i) + ": " + std::to_string(current_joint_values[i]);
                message += "     X : " + std::to_string(x) + " Y : " + std::to_string(y) + " Z : " + std::to_string(z);
                return message;
            };
            response->message = print_pose();
            response->success = true;
        }

    private:
        std::shared_ptr<moveit::planning_interface::MoveGroupInterface> move_group_interface_;
        rclcpp::Node::SharedPtr node_;
        rclcpp::Service<example_interfaces::srv::Trigger>::SharedPtr print_state_server_;
        rclcpp::Service<ai_soft_touch_motion_planning_msgs::srv::Pick>::SharedPtr pick_and_place_server_;
        std::string planning_group_;
        std::vector<double> orientation_;
        std::vector<double> place_position_;
        std::vector<double> pick_offset_;
        std::vector<double> look_offset_;
        double height_of_movement_;
};

int main(int argc, char* argv[]){

    rclcpp::init(argc,argv);
    auto node = std::make_shared<rclcpp::Node>("pick_and_place_server");
    auto moveit_example = std::make_shared<PickPlace>(node);
    RCLCPP_INFO(node->get_logger(),"Started the tutorials node");
    rclcpp::spin(node);
    rclcpp::shutdown();
}