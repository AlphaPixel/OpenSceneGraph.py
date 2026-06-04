{ inputs, ... }:
let
    self = inputs.self;
in {
  flake.overlays.default = inputs.nixpkgs.lib.composeManyExtensions [
    self.overlays.dev
    (final: prev: {
      pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
        (python-final: python-prev: {
          osgpy = python-final.callPackage ./default.nix {
          };
        })
      ];
      openscenegraph = (prev.openscenegraph.override {
        withExamples = true;
        withApps = true;
      }).overrideAttrs (previousAttrs: {
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
    })
  ];

  perSystem = { system, config, pkgs, ... }: {
    _module.args.pkgs = import inputs.nixpkgs {
      inherit system;
      config = {
        allowUnfree = true;
      };
      overlays = [ self.overlays.default ];
    };

    packages.default = pkgs.python3Packages.osgpy;
    checks.run-unit-tests = pkgs.python3Packages.osgpy;
  };
}
