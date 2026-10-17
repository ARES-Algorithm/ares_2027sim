cmake_minimum_required(VERSION 3.8)
project(ares_2027sim)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY launch meshes worlds
  DESTINATION share/${PROJECT_NAME}
)

install(FILES ares_br_urdf/br.urdf
  DESTINATION share/${PROJECT_NAME}/ares_br_urdf)
install(DIRECTORY ares_br_urdf/meshes
  DESTINATION share/${PROJECT_NAME}/ares_br_urdf)
install(FILES scripts/prepare_br.py
  DESTINATION share/${PROJECT_NAME}/scripts)

install(
  PROGRAMS
    scripts/generate_robocon_2027_world.py
    scripts/reset_mustika.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_robocon_2027_world test/test_robocon_2027_world.py)
  ament_add_pytest_test(test_br_model test/test_br_model.py)
endif()

ament_package()
