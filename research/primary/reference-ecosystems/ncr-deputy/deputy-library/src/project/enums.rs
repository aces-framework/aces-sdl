use serde::{Deserialize, Serialize};

#[allow(clippy::upper_case_acronyms)]
#[derive(Debug, Serialize, Deserialize, PartialEq, Eq, Clone)]
pub enum OperatingSystem {
    AlmaLinux,
    AmazonLinux,
    Asianux,
    CentOS,
    Debian,
    DebianGNULinux,
    EComStation,
    Fedora,
    Flatcar,
    FreeBSD,
    KylinLinuxAdvancedServer,
    MacOs,
    MiracleLinux,
    NeoKylinLinuxAdvancedServer,
    OpenSuse,
    OracleLinux,
    OSX,
    Pardus,
    Photon,
    RedHatEnterpriseLinux,
    RockyLinux,
    SCOOpenServer,
    SCOUnixWare,
    Solaris,
    SUSELinuxEnterprise,
    Ubuntu,
    Windows10,
    Windows11,
    Windows2000,
    Windows7,
    Windows8,
    WindowsServer2003,
    WindowsServer2008,
    WindowsServer2012,
    WindowsServer2016,
    WindowsServer2019,
    WindowsServer2022,
    WindowsVista,
    WindowsXP,

    #[serde(other)]
    Unknown,
}

#[allow(non_camel_case_types)]
#[derive(Debug, Serialize, Deserialize, PartialEq, Eq, Clone)]
pub enum Architecture {
    amd64,
    arm64,
    armhf,
    i386,

    #[serde(other)]
    Unknown,
}

#[allow(clippy::upper_case_acronyms)]
#[derive(Debug, Serialize, PartialEq, Eq, Clone)]
pub enum VirtualMachineType {
    OVA,
    QCOW2,
    RAW,
}
