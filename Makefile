INCLUDE = $(shell pkg-config hidapi-hidraw --cflags)
LIBS = $(shell pkg-config hidapi-hidraw --libs)

all:
	@clang++ ${INCLUDE} ${LIBS} -std=c++17 -o pdc-control src/main.cpp
