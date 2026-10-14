// shield.cc
//
// Geant4 "shielding thickness" ray-tracer for a CubeSat, following the method of
// Seo et al., Current Applied Physics 12 (2012) 1541-1547.
//
// What it does:
//   For each calculation point (a PCB surface, the payload box center, ...) it
//   fires "geantinos" (fake particles that never interact) outward in many
//   directions covering the full 4*pi sky. Along each ray it adds up the
//   material it crosses, converted to an ALUMINUM-EQUIVALENT thickness
//   (length * density / density_of_aluminum). Results go to a CSV file.
//
// What it does NOT do:
//   It does not compute dose. You combine the CSV with a dose-depth curve from
//   SPENVIS using tid.py (Eq. 1 in the paper).
//
// Usage:   ./shield [nCosTheta] [nPhi] [output.csv]
//          defaults: 30 60 rays.csv   (30*60 = 1800 sectors, same as the paper)
//
// ALL DIMENSIONS BELOW ARE PLACEHOLDERS. Replace them with your team's real 12U
// structure, PCB stack and payload dimensions before trusting any numbers.

#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "G4Box.hh"
#include "G4BaryonConstructor.hh"
#include "G4BosonConstructor.hh"
#include "G4Event.hh"
#include "G4LeptonConstructor.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4NistManager.hh"
#include "G4PVPlacement.hh"
#include "G4PhysicalConstants.hh"
#include "G4ParticleGun.hh"
#include "G4ParticleTable.hh"
#include "G4RunManagerFactory.hh"
#include "G4Step.hh"
#include "G4SubtractionSolid.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "G4UserEventAction.hh"
#include "G4UserSteppingAction.hh"
#include "G4VSolid.hh"
#include "G4VUserActionInitialization.hh"
#include "G4VUserDetectorConstruction.hh"
#include "G4VUserPhysicsList.hh"
#include "G4VUserPrimaryGeneratorAction.hh"

// ---------------------------------------------------------------------------
// A named point where we want to know the shielding.
// ---------------------------------------------------------------------------
struct CalcPoint {
  std::string name;
  G4ThreeVector pos;
};

// ---------------------------------------------------------------------------
// Geometry
// ---------------------------------------------------------------------------
class DetectorConstruction : public G4VUserDetectorConstruction {
 public:
  G4VPhysicalVolume* Construct() override {
    fPoints.clear();

    auto* nist = G4NistManager::Instance();
    auto* vac = nist->FindOrBuildMaterial("G4_Galactic");
    auto* al = nist->FindOrBuildMaterial("G4_Al");
    auto* si = nist->FindOrBuildMaterial("G4_Si");

    // Rough FR4 (PCB) stand-in: 60% SiO2 + 40% polyethylene by mass.
    // Fine for a 1.6 mm board when all we need is aluminum-equivalent thickness.
    auto* fr4 = new G4Material("FR4_approx", 1.85 * g / cm3, 2);
    fr4->AddMaterial(nist->FindOrBuildMaterial("G4_SILICON_DIOXIDE"), 60. * perCent);
    fr4->AddMaterial(nist->FindOrBuildMaterial("G4_POLYETHYLENE"), 40. * perCent);

    // ----- PLACEHOLDER DIMENSIONS -----
    const G4double Lx = 226.3 * mm, Ly = 226.3 * mm, Lz = 340.5 * mm;  // outer 12U envelope
    const G4double wall = 2.0 * mm;                                    // aluminum structure wall
    const G4double panelT = 1.6 * mm;                                  // solar panel thickness
    const G4double pcbX = 90. * mm, pcbY = 90. * mm, pcbT = 1.6 * mm;  // each PCB
    const G4double pcbPitch = 15. * mm;                                // spacing between PCBs
    const int nPCB = 5;
    const G4double plX = 90. * mm, plY = 90. * mm, plZ = 150. * mm;    // payload box (outer)
    const G4double plWall = 2.0 * mm;                                  // payload box wall

    // World: vacuum, big enough to contain everything with room to spare.
    auto* worldS = new G4Box("World", 0.5 * m, 0.5 * m, 0.6 * m);
    auto* worldLV = new G4LogicalVolume(worldS, vac, "World");
    auto* worldPV = new G4PVPlacement(nullptr, G4ThreeVector(), worldLV, "World", nullptr, false, 0, true);

    // Small helper: make a logical volume and place it in the world.
    auto place = [&](G4VSolid* s, G4Material* m, const G4String& name, const G4ThreeVector& p) {
      auto* lv = new G4LogicalVolume(s, m, name);
      new G4PVPlacement(nullptr, p, lv, name, worldLV, false, 0, true);
    };

    // 1) Structure: hollow aluminum box (outer box minus inner box).
    {
      auto* outer = new G4Box("StrOuter", Lx / 2, Ly / 2, Lz / 2);
      auto* inner = new G4Box("StrInner", Lx / 2 - wall, Ly / 2 - wall, Lz / 2 - wall);
      place(new G4SubtractionSolid("Structure", outer, inner), al, "Structure", G4ThreeVector());
    }

    // 2) Solar panels on all six outer faces (silicon plates as a rough stand-in).
    place(new G4Box("PanXp", panelT / 2, Ly / 2, Lz / 2), si, "PanelXp", G4ThreeVector((Lx + panelT) / 2, 0, 0));
    place(new G4Box("PanXm", panelT / 2, Ly / 2, Lz / 2), si, "PanelXm", G4ThreeVector(-(Lx + panelT) / 2, 0, 0));
    place(new G4Box("PanYp", Lx / 2, panelT / 2, Lz / 2), si, "PanelYp", G4ThreeVector(0, (Ly + panelT) / 2, 0));
    place(new G4Box("PanYm", Lx / 2, panelT / 2, Lz / 2), si, "PanelYm", G4ThreeVector(0, -(Ly + panelT) / 2, 0));
    place(new G4Box("PanZp", Lx / 2, Ly / 2, panelT / 2), si, "PanelZp", G4ThreeVector(0, 0, (Lz + panelT) / 2));
    place(new G4Box("PanZm", Lx / 2, Ly / 2, panelT / 2), si, "PanelZm", G4ThreeVector(0, 0, -(Lz + panelT) / 2));

    // 3) PCB stack. Calculation points sit 1 mm above each board's top surface,
    //    at the board center (same idea as the paper).
    const G4double zStart = -Lz / 2 + wall + 20. * mm;
    G4double zTopOfStack = 0;
    for (int i = 0; i < nPCB; ++i) {
      const G4double z = zStart + i * pcbPitch;
      const std::string nm = "PCB" + std::to_string(i + 1);
      place(new G4Box(nm, pcbX / 2, pcbY / 2, pcbT / 2), fr4, nm, G4ThreeVector(0, 0, z));
      fPoints.push_back({"pcb" + std::to_string(i + 1), G4ThreeVector(0, 0, z + pcbT / 2 + 1. * mm)});
      zTopOfStack = z + pcbT / 2;
    }

    // 4) Payload: hollow aluminum box above the PCB stack. Point = box center.
    {
      const G4double zc = zTopOfStack + 15. * mm + plZ / 2;
      auto* outer = new G4Box("PlOuter", plX / 2, plY / 2, plZ / 2);
      auto* inner = new G4Box("PlInner", plX / 2 - plWall, plY / 2 - plWall, plZ / 2 - plWall);
      place(new G4SubtractionSolid("Payload", outer, inner), al, "Payload", G4ThreeVector(0, 0, zc));
      fPoints.push_back({"payload_center", G4ThreeVector(0, 0, zc)});
    }

    return worldPV;
  }

  const std::vector<CalcPoint>& Points() const { return fPoints; }

 private:
  std::vector<CalcPoint> fPoints;
};

// ---------------------------------------------------------------------------
// Physics: we only need geantinos to move in straight lines, so the "physics
// list" is just particle definitions + transport. No data files required.
// ---------------------------------------------------------------------------
class RayPhysics : public G4VUserPhysicsList {
 public:
  void ConstructParticle() override {
    // Geantino lives in the boson constructor. Leptons/baryons are only here so
    // Geant4's production-cut tables find gamma, e-, e+ and proton.
    G4BosonConstructor boson;
    boson.ConstructParticle();
    G4LeptonConstructor lepton;
    lepton.ConstructParticle();
    G4BaryonConstructor baryon;
    baryon.ConstructParticle();
  }
  void ConstructProcess() override { AddTransportation(); }
};

// ---------------------------------------------------------------------------
// Event bookkeeping. ONE EVENT = ONE RAY.
//   event id -> (point index, cos(theta) bin, phi bin)
// The sky is cut into nCos x nPhi sectors of EQUAL solid angle (uniform bins in
// cos(theta) and phi), so every sector has dOmega = 4*pi / (nCos*nPhi).
// ---------------------------------------------------------------------------
class EventAction : public G4UserEventAction {
 public:
  EventAction(const DetectorConstruction* det, int nCos, int nPhi, std::ofstream* out)
      : fDet(det), fNSec(nCos * nPhi), fOut(out) {}

  void BeginOfEventAction(const G4Event*) override {
    fGeom = 0.;
    fAlEq = 0.;
  }

  // Called by the stepping action for every step of the geantino.
  void AddStep(G4double lengthGeom, G4double lengthAlEq) {
    fGeom += lengthGeom;
    fAlEq += lengthAlEq;
  }

  void EndOfEventAction(const G4Event* ev) override {
    const int id = ev->GetEventID();
    const int ip = id / fNSec;
    const int sector = id % fNSec;
    const double dOmega = 4. * CLHEP::pi / fNSec;
    (*fOut) << fDet->Points()[ip].name << ',' << ip << ',' << sector << ',' << dOmega << ',' << fGeom / mm << ','
            << fAlEq / mm << '\n';
  }

 private:
  const DetectorConstruction* fDet;
  int fNSec;
  std::ofstream* fOut;
  G4double fGeom = 0., fAlEq = 0.;
};

// ---------------------------------------------------------------------------
// Stepping: for each step, add up the material crossed.
// ---------------------------------------------------------------------------
class SteppingAction : public G4UserSteppingAction {
 public:
  explicit SteppingAction(EventAction* evt) : fEvt(evt) {}

  void UserSteppingAction(const G4Step* step) override {
    if (fRhoAl <= 0.) {  // look it up once, after the geometry exists
      fRhoAl = G4NistManager::Instance()->FindOrBuildMaterial("G4_Al")->GetDensity();
    }
    const G4double len = step->GetStepLength();
    const G4double rho = step->GetPreStepPoint()->GetMaterial()->GetDensity();
    // "Geometric" thickness counts only real material, not the vacuum.
    const G4double geom = (rho > 1e-3 * g / cm3) ? len : 0.;
    // Aluminum-equivalent thickness: weight by density relative to aluminum.
    fEvt->AddStep(geom, len * rho / fRhoAl);
  }

 private:
  EventAction* fEvt;
  G4double fRhoAl = 0.;
};

// ---------------------------------------------------------------------------
// Primary generator: aim the geantino according to the event id.
// ---------------------------------------------------------------------------
class PrimaryGenerator : public G4VUserPrimaryGeneratorAction {
 public:
  PrimaryGenerator(const DetectorConstruction* det, int nCos, int nPhi) : fDet(det), fNCos(nCos), fNPhi(nPhi) {
    fGun = new G4ParticleGun(1);
    fGun->SetParticleEnergy(1. * MeV);  // irrelevant for a geantino
  }
  ~PrimaryGenerator() override { delete fGun; }

  void GeneratePrimaries(G4Event* ev) override {
    if (fGun->GetParticleDefinition() == nullptr) {
      fGun->SetParticleDefinition(G4ParticleTable::GetParticleTable()->FindParticle("geantino"));
    }
    const int nSec = fNCos * fNPhi;
    const int id = ev->GetEventID();
    const int ip = id / nSec;       // which calculation point
    const int s = id % nSec;        // which sky sector
    const int ic = s / fNPhi;       // cos(theta) bin
    const int jp = s % fNPhi;       // phi bin

    // Aim at the CENTER of each sector.
    const double cosT = -1.0 + 2.0 * (ic + 0.5) / fNCos;
    const double sinT = std::sqrt(1.0 - cosT * cosT);
    const double phi = 2.0 * CLHEP::pi * (jp + 0.5) / fNPhi;

    fGun->SetParticlePosition(fDet->Points()[ip].pos);
    fGun->SetParticleMomentumDirection(G4ThreeVector(sinT * std::cos(phi), sinT * std::sin(phi), cosT));
    fGun->GeneratePrimaryVertex(ev);
  }

 private:
  const DetectorConstruction* fDet;
  int fNCos, fNPhi;
  G4ParticleGun* fGun = nullptr;
};

// ---------------------------------------------------------------------------
// Wire the actions together.
// ---------------------------------------------------------------------------
class ActionInitialization : public G4VUserActionInitialization {
 public:
  ActionInitialization(const DetectorConstruction* det, int nCos, int nPhi, std::ofstream* out)
      : fDet(det), fNCos(nCos), fNPhi(nPhi), fOut(out) {}

  void Build() const override {
    SetUserAction(new PrimaryGenerator(fDet, fNCos, fNPhi));
    auto* evt = new EventAction(fDet, fNCos, fNPhi, fOut);
    SetUserAction(evt);
    SetUserAction(new SteppingAction(evt));
  }

 private:
  const DetectorConstruction* fDet;
  int fNCos, fNPhi;
  std::ofstream* fOut;
};

// ---------------------------------------------------------------------------
int main(int argc, char** argv) {
  int nCos = 30, nPhi = 60;
  std::string outName = "rays.csv";
  if (argc > 1) nCos = std::atoi(argv[1]);
  if (argc > 2) nPhi = std::atoi(argv[2]);
  if (argc > 3) outName = argv[3];

  // Serial mode on purpose: one thread, events run in order, simple CSV output.
  auto* runManager = G4RunManagerFactory::CreateRunManager(G4RunManagerType::Serial);

  auto* det = new DetectorConstruction();
  runManager->SetUserInitialization(det);
  runManager->SetUserInitialization(new RayPhysics());

  std::ofstream out(outName);
  out << "point,point_index,sector,dOmega_sr,geom_mm,Al_equiv_mm\n";
  runManager->SetUserInitialization(new ActionInitialization(det, nCos, nPhi, &out));

  runManager->Initialize();  // builds the geometry, which fills det->Points()

  const int nEvents = static_cast<int>(det->Points().size()) * nCos * nPhi;
  std::cout << "Tracing " << nEvents << " rays (" << det->Points().size() << " points x " << nCos * nPhi
            << " sectors)\n";
  runManager->BeamOn(nEvents);

  out.close();
  delete runManager;
  std::cout << "Wrote " << outName << "\n";
  return 0;
}
