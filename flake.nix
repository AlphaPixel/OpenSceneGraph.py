{
  description = "Flake for building OpensceneGraph.py";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    git-hooks.url = "github:cachix/git-hooks.nix";
  };

  outputs =
    {
      self,
      nixpkgs,
      git-hooks,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python3;
        localOverlay = final: prev: {
          # To force the GL_CORE context, set OSG_GL_CONTEXT_PROFILE_MASK to 1, (2 = use compatibility context)
          openscenegraph = prev.openscenegraph.overrideAttrs (previousAttrs: {
            cmakeFlags = previousAttrs.cmakeFlags ++ [
              "-DOPENGL_PROFILE=GLCORE"
              "-DOSG_GL3_AVAILABLE=ON"
              "-DOSG_GL1_AVAILABLE=OFF"
              "-DOSG_GL2_AVAILABLE=OFF"
              "-DOSG_GLES1_AVAILABLE=OFF"
              "-DOSG_GLES2_AVAILABLE=OFF"
              "-DOSG_GL_DISPLAYLISTS_AVAILABLE=OFF"
              "-DOSG_GL_FIXED_FUNCTION_AVAILABLE=OFF"
              "-DOSG_GL_MATRICES_AVAILABLE=OFF"
              "-DOSG_GL_VERTEX_ARRAY_FUNCS_AVAILABLE=OFF"
              "-DOSG_GL_VERTEX_FUNCS_AVAILABLE=OFF"
            ];
          });
        };
        osgpy = python.pkgs.buildPythonPackage {
          pname = "openscenegraph";
          version = "0.1.0";
          format = "pyproject";
          src = ./.;

          dontUseCmakeConfigure = true;
          passthru = {
            pythonModule = pkgs.python3;
          };

          # Tools needed on the host to build the package
          nativeBuildInputs = [
            pkgs.cmake
            pkgs.ninja # Often used with CMake for faster builds
            python.pkgs.setuptools # Required for the install phase
            python.pkgs.scikit-build-core
          ];

          # Libraries or Python dependencies needed
          buildInputs = [
            python.pkgs.pybind11 # Common for C++/Python bindings
            pkgs.libGL
            pkgs.libpng
            pkgs.openscenegraph
            pkgs.mesa-gl-headers
          ];

          # Ensure dependencies are available at runtime
          propagatedBuildInputs = [
            python.pkgs.numpy
          ];

          # Optional: Pass specific flags to CMake
          cmakeFlags = [
            "-DCMAKE_BUILD_TYPE=Release"
          ];
        };

      in
      {
        packages.default = osgpy;

        checks.${system} = {
          inputsFrom = [ self.packages.${system}.default ];
          pre-commit-check = git-hooks.lib.${system}.run {
            src = ./.;
            hooks = {
              nixfmt.enable = true;
            };
          };
        };

        # Development shell for local testing
        devShells.default = pkgs.mkShell {
          inputsFrom = [ self.packages.${system}.default ];
          buildInputs = [
            pkgs.cmake-format
            pkgs.nixfmt
            pkgs.pre-commit
            python.pkgs.pytest
            osgpy
            (python.withPackages (ps: [
              ps.numpy
            ]))
          ];
          shellHook = ''
            #export PYTHONPATH="${self.packages.${system}.default}/lib/python3.11/site-packages:$PYTHONPATH"
            export PYTHONPATH="$PYTHONPATH:."
          '';
        };
      }
    );
}
