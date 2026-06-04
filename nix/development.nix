{ inputs, ... }:
let
  self = inputs.self;
  nixpkgs = inputs.nixpkgs;
in {
  flake.overlays.dev = nixpkgs.lib.composeManyExtensions [
    # NOTE: Put development overlays here.
  ];

  perSystem = { system, pkgs-dev, lib, pkgs, ... }: {
    _module.args.pkgs-dev = import nixpkgs {
      inherit system;
      overlays = [ self.overlays.dev self.overlays.default ];
    };

    devShells.default = pkgs-dev.mkShell rec {
      name = "pyosg-devshell";

      nativeBuildInputs = with pkgs-dev; [
        openscenegraph
      ];

      packages = with pkgs-dev; [
        (python3.withPackages (p:
          with p; [
            numpy
            pybind11
          ]))
        openscenegraph
        llvmPackages.clang
        cmake
        clang-tools
        spdlog
        gtest
      ];

      shellHook = ''
        # Find the site-packages directory inside ./result and add it to PYTHONPATH
        export PYTHONPATH="$(pwd)/result/${pkgs.python3.sitePackages}:$PYTHONPATH"
      '';
    };
  };
}
