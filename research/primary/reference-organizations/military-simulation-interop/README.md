# Military Simulation Interoperability Sources

This folder collects official and organization-owned primary materials for the
U.S./NATO military simulation interoperability stack. The intent is to capture
the standards, profiles, repositories, and program materials that explain how
large distributed live/virtual/constructive environments are actually made to
work in practice.

## Archived Local Copies

- `army-regulation-5-11-modeling-and-simulation.pdf`
  - Official U.S. Army regulation covering M&S governance, VV&A, and the
    designation of HLA as the standard technical architecture for DoD
    simulations.
  - Source:
    <https://www.govinfo.gov/content/pkg/GOVPUB-D101-PURL-LPS1042/pdf/GOVPUB-D101-PURL-LPS1042.pdf>

- `nistir-7785-distributed-simulation-standards-overview.pdf`
  - Official NIST report surveying modeling and simulation resources and
    distributed simulation standards, including DIS and HLA.
  - Source:
    <https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir7785.pdf>

- `trmc-tena-about.html`
  - Official TRMC overview of the Test and Training Enabling Architecture
    (TENA), including middleware, repository, object models, logical archive,
    tools, and gateways.
  - Source: <https://www.trmc.osd.mil/tena-about.html>

- `trmc-tena-home.html`
  - Official TRMC landing page for TENA and introductory material.
  - Source: <https://www.trmc.osd.mil/tena-home.html>

- `trmc-jmetc-101-2023-07-11-dista.pdf`
  - Official JMETC/TENA tutorial deck showing how TENA sits inside distributed
    live/virtual/constructive test and training.
  - Source:
    <https://www.trmc.osd.mil/attachments/JMETC-101-2023-07-11-DistA.pdf>

- `trmc-jmetc-overview-2024-02-29-dista.pdf`
  - Official JMETC overview fact sheet.
  - Source:
    <https://www.trmc.osd.mil/attachments/JMETC-Overview-FS-2024-02-29-DistA.pdf>

- `ieee-1516-2025-overview.html`
  - Official IEEE standards landing page for HLA Framework and Rules.
  - Source: <https://standards.ieee.org/ieee/1516/6687>

- `ieee-1516.2-2025-omt-overview.html`
  - Official IEEE standards landing page for HLA Object Model Template (OMT).
  - Source: <https://standards.ieee.org/ieee/1516.2/6689/>

- `ieee-1278.1-2012-dis-overview.html`
  - Official IEEE standards landing page for DIS Application Protocols.
  - Source: <https://standards.ieee.org/ieee/1278.1/4949>

- `ieee-1730-dseep-overview.html`
  - Official IEEE standards landing page for DSEEP.
  - Source: <https://standards.ieee.org/ieee/1730/4280/>

- `siso-ref-080-2023-hla-library-nomenclature.pdf`
  - Official SISO reference product for HLA runtime-library nomenclature,
    showing ongoing post-standard maintenance around deployed HLA products.
  - Source:
    <https://cdn.ymaws.com/www.sisostandards.org/resource/resmgr/reference_documents_/siso-ref-080-2023.pdf>

- `nisp-siso-hla.html`
  - Public NISP entry for HLA.
  - Source: <https://nisp.nw3.dk/standard/siso-hla.html>

- `nisp-siso-rpr-fom.html`
  - Public NISP entry for the Real-time Platform Reference Federation Object
    Model (RPR FOM).
  - Source: <https://nisp.nw3.dk/standard/siso-rpr-fom.html>

- `nisp-siso-enumerations.html`
  - Public NISP entry for SISO enumerations spanning HLA, DIS, and related
    architectures.
  - Source: <https://nisp.nw3.dk/standard/siso-enum.html>

## Consulted But Not Mirrored Locally

- NETN standards pages
  - These were consulted via the browser, but `netn.mscoe.org` repeatedly
    failed DNS resolution from the shell in this environment, so local HTML
    snapshots were not created.
  - Standards overview: <https://netn.mscoe.org/standards>
  - MSDL module page: <https://netn.mscoe.org/netn-modules/msdl>

## Why These Sources Matter

Taken together, these sources show that military simulation interoperability is
not one standard or one runtime. It is a layered ecosystem with:

- governance and VV&A policy
- scenario initialization standards
- runtime interaction architectures
- shared object models and enumerations
- engineering processes for federation design and execution
- operational middleware, repositories, gateways, and training infrastructure
