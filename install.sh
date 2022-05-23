#!/bin/bash

# download prerequisites
# git clone -b master14 https://github.com/smtrat/carl
# git clone https://github.com/moves-rwth/pycarl.git
# wget https://zenodo.org/record/4288652/files/moves-rwth/storm-1.6.3.zip
# wget https://github.com/moves-rwth/stormpy/archive/1.6.3.zip

set -ex

INSTALL_OFFLINE=false
INSTALL_DEPENDENCIES=true

if [ "$INSTALL_OFFLINE" = true ] || [ "$INSTALL_DEPENDENCIES" = true ]; then
    if [[ ! $(sudo echo 0) ]]; then echo "sudo authentication failed"; exit; fi
fi

THREADS=$(nproc)
# THREADS=1 # uncomment this to disable multi-core compilation

SYNTHESIS=`pwd`
PREREQUISITES=$SYNTHESIS/prerequisites
DOWNLOADS=$PREREQUISITES/downloads
TACAS_DEPENDENCIES=$PREREQUISITES/tacas-dependencies
SYNTHESIS_ENV=$SYNTHESIS/env

# unzip downloaded prerequisites
cd $PREREQUISITES
unzip $DOWNLOADS/carl.zip
mv carl-master14 carl
unzip $DOWNLOADS/pycarl.zip
mv pycarl-master pycarl
cd $SYNTHESIS

# dependencies
if [ "$INSTALL_DEPENDENCIES" = true ]; then
    # not installed on sarka (+ means there is an included resourse):
        # carl:
            # libcln-dev (+, requires texinfo)
            # libginac-dev (+)
            # libeigen3-dev (+)
        # storm:
            # libglpk-dev (+)
            # libxerces-c-dev (we probably do not need --gspn)

    sudo apt update
    sudo apt -y install build-essential git automake cmake libboost-all-dev libcln-dev libgmp-dev libginac-dev libglpk-dev libhwloc-dev libz3-dev libxerces-c-dev libeigen3-dev
    sudo apt -y install texlive-latex-extra
    sudo apt -y install maven uuid-dev python3-dev libffi-dev libssl-dev python3-pip virtualenv
    sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 10
fi

# offline dependencies
if [ "$INSTALL_OFFLINE" = true ]; then
    sudo echo "export PATH=$PATH:$HOME/.local/bin" >> $HOME/.profile
    source $HOME/.profile
    cd $TACAS_DEPENDENCIES
    unzip storm-eigen.zip
    pip3 install --no-index -f pip-packages -r python-requirements
    sudo dpkg -i apt-packages/*.deb
    cd $SYNTHESIS
fi

# set up python environment
virtualenv -p python3 $SYNTHESIS_ENV
source $SYNTHESIS_ENV/bin/activate
if [ "$INSTALL_OFFLINE" = true ]; then
    cd $TACAS_DEPENDENCIES
    pip3 install --no-index -f pip-packages -r python-requirements
    cd $SYNTHESIS
else
    pip3 install pytest pytest-runner pytest-cov numpy scipy pysmt z3-solver click
fi
deactivate

# carl
cd $PREREQUISITES
mkdir -p carl/build
cd carl/build
cmake -DUSE_CLN_NUMBERS=ON -DUSE_GINAC=ON -DTHREAD_SAFE=ON ..
make lib_carl --jobs $THREADS
#[TEST] make test
cd $SYNTHESIS

#pycarl
cd $PREREQUISITES/pycarl
source $SYNTHESIS_ENV/bin/activate
python3 setup.py build_ext --jobs $THREADS --disable-parser develop
#[TEST] python3 setup.py test
deactivate
cd $SYNTHESIS

# storm
mkdir -p $SYNTHESIS/storm/build
if [ "$INSTALL_TACAS21" = true ]; then
    cp $TACAS_DEPENDENCIES/storm_3rdparty_CMakeLists.txt $SYNTHESIS/storm/resources/3rdparty/CMakeLists.txt
    mkdir -p $SYNTHESIS/storm/build/include/resources/3rdparty/
    cp -r $TACAS_DEPENDENCIES/StormEigen/ $SYNTHESIS/storm/build/include/resources/3rdparty/
fi
cd $SYNTHESIS/storm/build
cmake ..
make storm-main storm-synthesis --jobs $THREADS
#[TEST] make check --jobs $THREADS
cd $SYNTHESIS

# stormpy
cd $SYNTHESIS/stormpy
source $SYNTHESIS_ENV/bin/activate
python3 setup.py build_ext --jobs $THREADS develop
#[TEST] python3 setup.py test
deactivate
cd $SYNTHESIS

# paynt
cd $SYNTHESIS/paynt
source $SYNTHESIS_ENV/bin/activate
python3 setup.py install
#[TEST] python3 setup.py test
deactivate
cd $SYNTHESIS

# tacas21-install

# test
# source env/bin/activate
# python3 paynt/paynt.py --project tacas21-benchmark/grid --properties easy.properties hybrid
