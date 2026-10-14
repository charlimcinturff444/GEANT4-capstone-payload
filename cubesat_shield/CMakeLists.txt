cmake_minimum_required(VERSION 3.16)
project(cubesat_shield)

find_package(Geant4 REQUIRED)
include(${Geant4_USE_FILE})

add_executable(shield shield.cc)
target_link_libraries(shield ${Geant4_LIBRARIES})
