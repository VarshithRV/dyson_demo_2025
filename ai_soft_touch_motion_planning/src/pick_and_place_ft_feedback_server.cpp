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
#include "geometry_msgs/msg/point.hpp"
#include "example_interfaces/srv/trigger.hpp"
#include "ai_soft_touch_motion_planning_msgs/srv/pick.hpp"
#include "ur_msgs/srv/set_io.hpp"
#include "geometry_msgs/msg/twist_stamped.hpp"
#include "geometry_msgs/msg/wrench_stamped.hpp"
#include "controller_manager_msgs/srv/switch_controller.hpp"
#include "std_srvs/srv/trigger.hpp"

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

            node_->declare_parameter<double>("place_step_x", 0.05);
            node_->declare_parameter<double>("place_step_y", 0.05);

            node_->declare_parameter<int>("pin_out1", 0);
            node_->declare_parameter<int>("pin_out2", 0);

            node_->declare_parameter<double>("ft_threshold", 5.0);

            node->declare_parameter<std::string>("arm_side","left");
            
            node_->declare_parameter<double>("height_of_movement", 0.25);

            node_->declare_parameter<std::string>("endeffector_link", "right_tool0");

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

            place_step_x_ = node_->get_parameter("place_step_x").as_double();
            place_step_y_ = node_->get_parameter("place_step_y").as_double();

            ft_threshold_ = node->get_parameter("ft_threshold").as_double();

            pin_out1_ = node->get_parameter("pin_out1").as_int();
            pin_out2_ = node->get_parameter("pin_out2").as_int();

            arm_side_ = node->get_parameter("arm_side").as_string();

            height_of_movement_=node->get_parameter("height_of_movement").as_double();

            endeffector_link_=node->get_parameter("endeffector_link").as_string();

            // Servo twist publisher
            std::string twist_topic =
                "/" + arm_side_ + "_servo_node_main/delta_twist_cmds";
            servo_twist_pub_ =
                node_->create_publisher<geometry_msgs::msg::TwistStamped>(twist_topic, 10);

            // Wrench subscriber
            std::string wrench_topic =
                "/" + arm_side_ + "_force_torque_sensor_broadcaster/wrench";
            wrench_sub_ = node_->create_subscription<geometry_msgs::msg::WrenchStamped>(
                wrench_topic, 10,
                std::bind(&PickPlace::wrench_callback, this, std::placeholders::_1));

            // Controller switch client
            std::string switch_srv =
                "/" + arm_side_ + "_controller_manager/switch_controller";
            switch_controller_client_ =
                node_->create_client<controller_manager_msgs::srv::SwitchController>(switch_srv);

            // Servo start/stop services
            std::string start_servo_srv =
                "/" + arm_side_ + "_servo_node_main/start_servo";
            std::string stop_servo_srv =
                "/" + arm_side_ + "_servo_node_main/stop_servo";

            start_servo_client_ =
                node_->create_client<std_srvs::srv::Trigger>(start_servo_srv);
            stop_servo_client_ =
                node_->create_client<std_srvs::srv::Trigger>(stop_servo_srv);

            // Zero FT service
            std::string zero_ft_srv =
                "/" + arm_side_ + "_io_and_status_controller/zero_ftsensor";
            zero_ft_client_ =
                node_->create_client<std_srvs::srv::Trigger>(zero_ft_srv);

            move_group_interface_ = std::make_shared<moveit::planning_interface::MoveGroupInterface>(node, planning_group_);

            move_group_interface_->setEndEffectorLink(endeffector_link_);
            move_group_interface_->setPlanningTime(10.0);
            move_group_interface_->setNumPlanningAttempts(15);
            move_group_interface_->setMaxVelocityScalingFactor(0.1);
            move_group_interface_->setMaxAccelerationScalingFactor(0.1);
            move_group_interface_->setPlannerId("RRTConnectkConfigDefault");
            move_group_interface_->startStateMonitor();

            rclcpp::sleep_for(3s);

            auto planning_frame = this->move_group_interface_->getPlanningFrame();
            RCLCPP_INFO(node->get_logger(),"Planning frame : %s",planning_frame.c_str());
            
            auto endeffector = this-> move_group_interface_->getEndEffectorLink();
            RCLCPP_INFO(node->get_logger(),"End Effector Link : %s",endeffector.c_str());
            
            auto current_pose = this->move_group_interface_->getCurrentPose(endeffector); // this consistently returns a wrong value dont know why, some executor shit
            RCLCPP_INFO(node->get_logger(), "x : %f, y : %f, z : %f",current_pose.pose.position.x,current_pose.pose.position.y,current_pose.pose.position.z);

            print_state_server_= node_->create_service<example_interfaces::srv::Trigger>("~/print_robot_state",std::bind(&PickPlace::print_state,this,std::placeholders::_1,std::placeholders::_2));
            pick_and_place_server_ = node_->create_service<ai_soft_touch_motion_planning_msgs::srv::Pick>("~/pick_and_place",std::bind(&PickPlace::pick_and_place_server,this,std::placeholders::_1,std::placeholders::_2));
            std::string io_service_name = arm_side_ + "_io_and_status_controller";
            set_io_client_ = node_->create_client<ur_msgs::srv::SetIO>(io_service_name);

            if(!set_io_client_->wait_for_service(3s))
                RCLCPP_ERROR(node_->get_logger(),"Set IO client service is not connected!");

        }

        void gripper_on(){
            if(pin_out1_){
                ur_msgs::srv::SetIO_Request::SharedPtr request = std::make_shared<ur_msgs::srv::SetIO::Request>();
                request->fun = request->FUN_SET_DIGITAL_OUT;
                request->pin = pin_out1_;
                request->state = request->STATE_ON;
                auto result = set_io_client_->async_send_request(request);
                RCLCPP_INFO(node_->get_logger(),"Gripper on");
            }
            if(pin_out2_){
                ur_msgs::srv::SetIO_Request::SharedPtr request = std::make_shared<ur_msgs::srv::SetIO::Request>();
                request->fun = request->FUN_SET_DIGITAL_OUT;
                request->pin = pin_out2_;
                request->state = request->STATE_ON;
                auto result = set_io_client_->async_send_request(request);
                RCLCPP_INFO(node_->get_logger(),"Gripper on");
            }
        }
        
        void gripper_off(){
            if(pin_out1_){
                ur_msgs::srv::SetIO_Request::SharedPtr request = std::make_shared<ur_msgs::srv::SetIO::Request>();
                request->fun = request->FUN_SET_DIGITAL_OUT;
                request->pin = pin_out1_;
                request->state = request->STATE_OFF;
                auto result = set_io_client_->async_send_request(request);
                RCLCPP_INFO(node_->get_logger(),"Gripper off");
            }
            if(pin_out2_){
                ur_msgs::srv::SetIO_Request::SharedPtr request = std::make_shared<ur_msgs::srv::SetIO::Request>();
                request->fun = request->FUN_SET_DIGITAL_OUT;
                request->pin = pin_out2_;
                request->state = request->STATE_OFF;
                auto result = set_io_client_->async_send_request(request);
                RCLCPP_INFO(node_->get_logger(),"Gripper off");
            }
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

        void guarded_ft_servo_approach()
        {
            constexpr double approach_distance = 0.15;   // HARDCODED MAX DISTANCE
            constexpr double approach_speed    = 0.01;   // 0.01 m/s along -Z  HARDCODED

            auto switch_req =
                std::make_shared<controller_manager_msgs::srv::SwitchController::Request>();

            switch_req->start_controllers = {
                arm_side_ + "_forward_position_controller"};
            switch_req->stop_controllers = {
                arm_side_ + "_scaled_joint_trajectory_controller"};
            switch_req->strictness =
                controller_manager_msgs::srv::SwitchController::Request::STRICT;
            switch_req->start_asap = true;
            switch_req->timeout = builtin_interfaces::msg::Duration();
            switch_req->timeout.sec = 5;
            switch_req->timeout.nanosec = 0;

            if (!switch_controller_client_->wait_for_service(2s))
            {
                RCLCPP_ERROR(node_->get_logger(),
                             "[guarded_ft_servo_approach] switch_controller service unavailable");
                return;
            }

            {
                auto future = switch_controller_client_->async_send_request(switch_req);
                if (future.wait_for(5s) != std::future_status::ready ||
                    !future.get()->ok)
                {
                    RCLCPP_ERROR(node_->get_logger(),
                                 "[guarded_ft_servo_approach] Failed to switch controllers");
                    return;
                }
            }

            if (!zero_ft_client_->wait_for_service(2s))
            {
                RCLCPP_ERROR(node_->get_logger(),
                             "[guarded_ft_servo_approach] zero_ftsensor service unavailable");
                return;
            }

            {
                auto zero_req = std::make_shared<std_srvs::srv::Trigger::Request>();
                auto future = zero_ft_client_->async_send_request(zero_req);
                if (future.wait_for(5s) != std::future_status::ready ||
                    !future.get()->success)
                {
                    RCLCPP_ERROR(node_->get_logger(),
                                 "[guarded_ft_servo_approach] zero_ftsensor call failed");
                    return;
                }
            }

            // ------------------------------------------------------------------
            // 4) Start servo: /{arm_side_}_servo_node_main/start_servo
            // ------------------------------------------------------------------
            if (!start_servo_client_->wait_for_service(2s))
            {
                RCLCPP_ERROR(node_->get_logger(),
                             "[guarded_ft_servo_approach] start_servo service unavailable");
                return;
            }

            {
                auto trig_req = std::make_shared<std_srvs::srv::Trigger::Request>();
                auto future = start_servo_client_->async_send_request(trig_req);
                if (future.wait_for(5s) != std::future_status::ready ||
                    !future.get()->success)
                {
                    RCLCPP_ERROR(node_->get_logger(),
                                 "[guarded_ft_servo_approach] start_servo call failed");
                    return;
                }
            }
            have_wrench_ = false;
            double travelled = 0.0;
            rclcpp::Rate rate(100.0); 
            const double dt = 1.0 / 100.0;

            while (rclcpp::ok() && travelled < approach_distance)
            {
                if (have_wrench_)
                {
                    double fz = last_wrench_.wrench.force.z;
                    if (std::abs(fz) > ft_threshold_)
                    {
                        RCLCPP_INFO(node_->get_logger(),
                                    "[guarded_ft_servo_approach] Contact detected, Fz=%.3f",
                                    fz);
                        break;
                    }
                }

                geometry_msgs::msg::TwistStamped cmd;
                cmd.header.stamp = node_->now();
                cmd.header.frame_id = endeffector_link_;  
                cmd.twist.linear.x = 0.0;
                cmd.twist.linear.y = 0.0;
                cmd.twist.linear.z = -approach_speed; 

                servo_twist_pub_->publish(cmd);

                travelled += approach_speed * dt;
                rate.sleep();
            }

            if (stop_servo_client_->wait_for_service(2s))
            {
                auto trig_req = std::make_shared<std_srvs::srv::Trigger::Request>();
                auto future = stop_servo_client_->async_send_request(trig_req);
                if (future.wait_for(5s) != std::future_status::ready ||
                    !future.get()->success)
                {
                    RCLCPP_WARN(node_->get_logger(),
                                "[guarded_ft_servo_approach] stop_servo call reported failure");
                }
            }
            else
            {
                RCLCPP_WARN(node_->get_logger(),
                            "[guarded_ft_servo_approach] stop_servo service unavailable");
            }

    
            auto switch_back_req =
                std::make_shared<controller_manager_msgs::srv::SwitchController::Request>();

            switch_back_req->start_controllers = {
                arm_side_ + "_scaled_joint_trajectory_controller"};
            switch_back_req->stop_controllers = {
                arm_side_ + "_forward_position_controller"};
            switch_back_req->strictness =
                controller_manager_msgs::srv::SwitchController::Request::STRICT;
            switch_back_req->start_asap = true;
            switch_back_req->timeout = builtin_interfaces::msg::Duration();
            switch_back_req->timeout.sec = 5;
            switch_back_req->timeout.nanosec = 0;

            if (switch_controller_client_->wait_for_service(2s))
            {
                auto future = switch_controller_client_->async_send_request(switch_back_req);
                if (future.wait_for(5s) != std::future_status::ready ||
                    !future.get()->ok)
                {
                    RCLCPP_WARN(node_->get_logger(),
                                "[guarded_ft_servo_approach] Failed to switch controllers back");
                }
            }
            else
            {
                RCLCPP_WARN(node_->get_logger(),
                            "[guarded_ft_servo_approach] switch_controller service unavailable (switch back)");
            }

            RCLCPP_INFO(node_->get_logger(),
                        "[guarded_ft_servo_approach] Finished guarded FT descent");
        }

        bool execute_waypoints(const std::vector<geometry_msgs::msg::Pose> waypoints){
            move_group_interface_->setStartStateToCurrentState();
            moveit_msgs::msg::RobotTrajectory trajectory;
            const double eef_step = 0.002;
            const double jump_threshold = 0.0;

            RCLCPP_INFO(node_->get_logger(), "Computing cartesian path");
            double fraction = move_group_interface_->computeCartesianPath(
                waypoints, eef_step, jump_threshold, trajectory);

            if (fraction < 1.0) {
                RCLCPP_ERROR(node_->get_logger(), "Cartesian path planning failed, fraction: %f", fraction);
                return false;
            }
        
            RCLCPP_INFO(node_->get_logger(),"Trajectory created attempting to execute now");

            moveit::planning_interface::MoveGroupInterface::Plan plan;
            plan.trajectory_ = trajectory;
        
            auto result = move_group_interface_->execute(plan);

            if (result != moveit::core::MoveItErrorCode::SUCCESS) {
                RCLCPP_ERROR(node_->get_logger(), "Cartesian path execution failed");
                return false;
            }
            move_group_interface_->setStartStateToCurrentState();
            return true;
        }

        void pick_and_place_server(const ai_soft_touch_motion_planning_msgs::srv::Pick_Request::SharedPtr request,ai_soft_touch_motion_planning_msgs::srv::Pick_Response::SharedPtr response){
            geometry_msgs::msg::Pose approx_pick;
            
            move_group_interface_->setStartStateToCurrentState();
            auto current_pose = this->move_group_interface_->getCurrentPose().pose;
            
            approx_pick.position = request->object_position;
            approx_pick.position.z += 0.07; // HARDCODED PRESERVO
            approx_pick.orientation.w = orientation_[0];
            approx_pick.orientation.x = orientation_[1];
            approx_pick.orientation.y = orientation_[2];
            approx_pick.orientation.z = orientation_[3];

            geometry_msgs::msg::Pose place;
            place.position.x = place_position_[0] + (((request->index)/2)*place_step_x_); // for placing in a grid pattern
            place.position.y = place_position_[1] - ((request->index)%2?:place_step_y_,0.0);
            place.position.z = place_position_[2];
            place.orientation.w = orientation_[0];
            place.orientation.x = orientation_[1];
            place.orientation.y = orientation_[2];
            place.orientation.z = orientation_[3];

            move_group_interface_->setStartStateToCurrentState();
            geometry_msgs::msg::Pose target = move_group_interface_->getCurrentPose(this->endeffector_link_).pose;
            
            std::vector<geometry_msgs::msg::Pose> waypoints;
            waypoints.push_back(target);

            geometry_msgs::msg::Pose look_pose = approx_pick;
            
            look_pose.position.x += look_offset_[0];
            look_pose.position.y += look_offset_[1];
            look_pose.position.z += look_offset_[2];
            waypoints.push_back(look_pose);
            
            if(!execute_waypoints(waypoints)){
                response->result=false;
                return;
            }
                
            std::this_thread::sleep_for(2s);
            // do perception here and then add the pick_offset_ biases here, set the orientation

            waypoints.clear();

            approx_pick.position.x += pick_offset_[0];
            approx_pick.position.y += pick_offset_[1];
            approx_pick.position.z += pick_offset_[2];
            waypoints.push_back(approx_pick);

            if(!execute_waypoints(waypoints)){
                response->result=false;
                return;
            }

            guarded_ft_servo_approach();

            std::this_thread::sleep_for(2s);
            // activate gripper here
            gripper_on();
            
            waypoints.clear();
            geometry_msgs::msg::Pose post_pick = approx_pick;
            post_pick.position.z = height_of_movement_;
            waypoints.push_back(post_pick);

            geometry_msgs::msg::Pose pre_place = place;
            pre_place.position.z = height_of_movement_;
            waypoints.push_back(pre_place);
            waypoints.push_back(place);

            if(!execute_waypoints(waypoints)){
                response->result=false;
                return;
            }
            // deactivate gripper here
            gripper_off();

            std::this_thread::sleep_for(2s);

            waypoints.clear();
            waypoints.push_back(pre_place);

            if(!execute_waypoints(waypoints)){
                response->result=false;
                return;
            }

            move_group_interface_->setStartStateToCurrentState();

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

        void wrench_callback(const geometry_msgs::msg::WrenchStamped::SharedPtr msg)
        {
            last_wrench_ = *msg;
            have_wrench_ = true;
        }

    private:
        std::shared_ptr<moveit::planning_interface::MoveGroupInterface> move_group_interface_;
        rclcpp::Node::SharedPtr node_;
        rclcpp::Service<example_interfaces::srv::Trigger>::SharedPtr print_state_server_;
        rclcpp::Service<ai_soft_touch_motion_planning_msgs::srv::Pick>::SharedPtr pick_and_place_server_;
        rclcpp::Client<ur_msgs::srv::SetIO>::SharedPtr set_io_client_;
        std::string planning_group_;
        std::vector<double> orientation_;
        std::vector<double> place_position_;
        std::vector<double> pick_offset_;
        std::vector<double> look_offset_;
        double height_of_movement_;
        std::string endeffector_link_;
        double place_step_x_, place_step_y_;
        int pin_out1_, pin_out2_;
        std::string arm_side_;
        double ft_threshold_;
        rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr servo_twist_pub_;
        rclcpp::Subscription<geometry_msgs::msg::WrenchStamped>::SharedPtr wrench_sub_;
        rclcpp::Client<controller_manager_msgs::srv::SwitchController>::SharedPtr switch_controller_client_;
        rclcpp::Client<std_srvs::srv::Trigger>::SharedPtr start_servo_client_;
        rclcpp::Client<std_srvs::srv::Trigger>::SharedPtr stop_servo_client_;
        rclcpp::Client<std_srvs::srv::Trigger>::SharedPtr zero_ft_client_;

        geometry_msgs::msg::WrenchStamped last_wrench_;
        bool have_wrench_{false};
};

int main(int argc, char* argv[]){

    rclcpp::init(argc,argv);
    auto node = std::make_shared<rclcpp::Node>("pick_and_place_ft_feedback_server");
    auto moveit_example = std::make_shared<PickPlace>(node);
    RCLCPP_INFO(node->get_logger(),"Started the tutorials node");
    rclcpp::spin(node);
    rclcpp::shutdown();
}