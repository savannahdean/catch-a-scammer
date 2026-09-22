# catch-a-scammer client -- plain Makefile
#
# Object files go under build/, so src/ only ever holds your source code.
#
#   Windows: build from an MSYS2 MINGW64 shell after installing:
#              pacman -S --needed mingw-w64-x86_64-gcc mingw-w64-x86_64-raylib \
#                mingw-w64-x86_64-curl mingw-w64-x86_64-nlohmann-json
#   Linux:   sudo apt install build-essential libcurl4-openssl-dev nlohmann-json3-dev
#   macOS:   brew install raylib nlohmann-json curl
#
# Targets:  make        build
#           make check  report which dependency is missing
#           make run    build and launch
#           make clean  delete the whole build/ folder

CXX      ?= g++
CXXFLAGS := -std=c++17 -O2 -Wall -Wextra -Isrc
BUILDDIR := build

SRCS := $(wildcard src/*.cpp) $(wildcard src/*/*.cpp)
OBJS := $(patsubst src/%.cpp,$(BUILDDIR)/%.o,$(SRCS))

# Library list depends on the target OS. Everything else (mkdir, rm) is the
# same everywhere because on Windows we build inside the MSYS2 shell, which
# provides the Unix commands.
ifeq ($(OS),Windows_NT)
    TARGET := catch-a-scammer.exe
    LDLIBS := -lraylib -lcurl -lopengl32 -lgdi32 -lwinmm
else
    TARGET  := catch-a-scammer
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Darwin)
        LDLIBS   := -lraylib -lcurl -framework CoreVideo -framework IOKit \
                    -framework Cocoa -framework GLUT -framework OpenGL
        CXXFLAGS += -I/opt/homebrew/include
        LDFLAGS  += -L/opt/homebrew/lib
    else
        LDLIBS   := -lraylib -lcurl -lGL -lm -lpthread -ldl -lrt -lX11
    endif
endif

ifneq ($(wildcard vendor/nlohmann/json.hpp),)
    CXXFLAGS += -Ivendor
endif

.PHONY: all clean run check

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(LDFLAGS) -o $@ $(OBJS) $(LDLIBS)
	@echo "built $(TARGET)"

$(BUILDDIR)/%.o: src/%.cpp
	@mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -c $< -o $@

run: $(TARGET)
	./$(TARGET)

check:
	@echo "checking raylib  (src/main.cpp)"
	$(CXX) $(CXXFLAGS) -fsyntax-only src/main.cpp
	@echo "checking libcurl (src/net/http.cpp)"
	$(CXX) $(CXXFLAGS) -fsyntax-only src/net/http.cpp
	@echo "checking json    (src/core/session.cpp)"
	$(CXX) $(CXXFLAGS) -fsyntax-only src/core/session.cpp
	@echo "all dependencies OK"

clean:
	rm -rf $(BUILDDIR) $(TARGET) catch-a-scammer catch-a-scammer.exe
