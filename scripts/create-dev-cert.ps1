param(
  [string]$IpAddress = "172.16.166.159",
  [string]$Password = "signlink-dev"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path "$PSScriptRoot\.."
$certDir = Join-Path $root "certs"
New-Item -ItemType Directory -Force -Path $certDir | Out-Null

$pfxPath = Join-Path $certDir "sign-link-dev.pfx"
$cerPath = Join-Path $certDir "sign-link-dev.cer"
$passwordSecure = ConvertTo-SecureString -String $Password -Force -AsPlainText

$rsa = [System.Security.Cryptography.RSA]::Create(2048)
$subject = [System.Security.Cryptography.X509Certificates.X500DistinguishedName]::new("CN=Sign Link Local Dev")
$request = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
  $subject,
  $rsa,
  [System.Security.Cryptography.HashAlgorithmName]::SHA256,
  [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
)

$sanBuilder = [System.Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new()
$sanBuilder.AddDnsName("localhost")
$sanBuilder.AddIpAddress([System.Net.IPAddress]::Parse("127.0.0.1"))
$sanBuilder.AddIpAddress([System.Net.IPAddress]::Parse($IpAddress))

$request.CertificateExtensions.Add($sanBuilder.Build())
$request.CertificateExtensions.Add(
  [System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($false, $false, 0, $true)
)
$request.CertificateExtensions.Add(
  [System.Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new(
    [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::DigitalSignature,
    $true
  )
)

$eku = [System.Security.Cryptography.OidCollection]::new()
$eku.Add([System.Security.Cryptography.Oid]::new("1.3.6.1.5.5.7.3.1")) | Out-Null
$request.CertificateExtensions.Add(
  [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]::new($eku, $true)
)

$notBefore = [System.DateTimeOffset]::Now.AddDays(-1)
$notAfter = $notBefore.AddYears(2)
$certificate = $request.CreateSelfSigned($notBefore, $notAfter)
if ($certificate.HasPrivateKey) {
  $certificateWithKey = $certificate
} else {
  $certificateWithKey = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::CopyWithPrivateKey($certificate, $rsa)
}

[System.IO.File]::WriteAllBytes(
  $pfxPath,
  $certificateWithKey.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Pfx, $Password)
)
[System.IO.File]::WriteAllBytes(
  $cerPath,
  $certificate.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
)

Write-Host "Created Vite HTTPS certificate:"
Write-Host "  PFX: $pfxPath"
Write-Host "  CER: $cerPath"
Write-Host ""
Write-Host "Trust this CER on each laptop that opens the dev site:"
Write-Host "  Import-Certificate -FilePath `"$cerPath`" -CertStoreLocation Cert:\CurrentUser\Root"
