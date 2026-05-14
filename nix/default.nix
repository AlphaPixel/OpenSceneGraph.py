{ lib
  , buildPythonPackage
  , pythonOlder
  , cmake
  , scikit-build-core
  , ninja
  , pybind11
  , spdlog
  , openscenegraph
  , mesa-gl-headers
  , libGL
  , numpy
  , pkgs
  , stdenv
}:

buildPythonPackage.override { stdenv = pkgs.clangStdenv; } rec {
  pname = "pyosg";
  version = "1.0.0";
  pyproject = true;
  disabled = pythonOlder "3.8";

  src = ../.;
  dontStrip = true;

  build-system = [ scikit-build-core ninja cmake pybind11 ];
  dontUseCmakeConfigure = true;

  # macOS needs to leave Python symbols undefined for dynamic lookup at runtime
  NIX_LDFLAGS = lib.optionalString stdenv.isDarwin "-undefined dynamic_lookup";

  # Ensure the compiler doesn't hide everything by default
  # This can be set in CMake or here as a fallback
  CXXFLAGS = "-fvisibility=default";

  dependencies = [
    numpy
  ];

  buildInputs = [
    mesa-gl-headers
    libGL
    openscenegraph
    spdlog
  ];

  pythonImportCheck = [ "osgpy" ];

  meta = with lib; {
    description = ''
       Python bindings for OpenSceneGraph (OSG)
    '';
    license = licenses.mit;
    maintainers = with maintainers; [ breakds ];
  };
}
