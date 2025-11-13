#include <iostream>
#include <string>
#include <cstdlib>
#include <cstring>
#include <array>
#include <vector>
#include <sstream>
#include <iomanip>
#include "Insection.h"
#include "psi/server.h"
#include "psi/common/stopwatch.h"
#include "psi/common/thread_pool_mgr.h"
#include <fstream>
#include <chrono>

void printHelp() {
    std::cout << "Usage: Client_cli " << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -h, --help     Display this help message" << std::endl;
}

std::vector<std::vector<uint8_t>> readSendershareBytes() {
    std::vector<std::vector<uint8_t>> sendershare_bytes;
    std::string filename = "/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/sendershare_binary_with_bytes.txt";
    
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cout << "Warning: Cannot open " << filename << std::endl;
        return sendershare_bytes;
    }
    
    std::string line;
    while (std::getline(file, line)) {
        if (line.empty()) continue;
        
        // 解析格式: "二进制字符串 十六进制字节"
        std::istringstream iss(line);
        std::string binary_str, hex_str;
        iss >> binary_str >> hex_str;
        
        if (!hex_str.empty()) {
            // 将十六进制字符串转换为字节数组
            std::vector<uint8_t> bytes;
            for (size_t i = 0; i < hex_str.length(); i += 2) {
                std::string byte_str = hex_str.substr(i, 2);
                uint8_t byte_val = static_cast<uint8_t>(std::stoul(byte_str, nullptr, 16));
                bytes.push_back(byte_val);
            }
            sendershare_bytes.push_back(bytes);
        }
    }
    
    file.close();
    std::cout << "Loaded " << sendershare_bytes.size() << " lines from sendershare_binary_with_bytes.txt" << std::endl;
    return sendershare_bytes;
}
struct clientparams{
    size_t threads;
    size_t setsize;
    size_t logsetsize;
    size_t inssize=1;
}cmdparams;

int PerfromCMD(int argc, char* argv[]){
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-h" || arg == "--help") {
            printHelp();
            return 0;
        } else if (arg == "-t" || arg == "--threads") {
            if (i + 1 < argc) {
                cmdparams.threads = std::atoi(argv[i + 1]);
                ++i;
            } else {
                std::cerr << "Error: No number provided after " << arg << std::endl;
                return 1;
            }
        } else if (arg == "-l" || arg == "--log"){
            if (i + 1 < argc) {
                cmdparams.logsetsize =  std::atoi(argv[i + 1]);
                cmdparams.setsize = 1 << cmdparams.logsetsize;
                ++i;
            } else {
                std::cerr << "Error: No number provided after " << arg << std::endl;
                return 1;
            }
        } else if (arg == "-i" || arg == "--ins"){
            if (i + 1 < argc) {
                cmdparams.inssize = std::atoi(argv[i + 1]);
                ++i;
            } else {
                std::cerr << "Error: No number provided after " << arg << std::endl;
                return 1;
            }
        }
        else {
            printHelp();
            std::cerr << "Error: Unknown option " << arg << std::endl;
            return 1;
        }
    }

    std::cout << "threads: " << cmdparams.threads << std::endl;
    std::cout << "Client Set size: " << cmdparams.setsize << "(2^"<< cmdparams.logsetsize << ")" << std::endl;
    std::cout << "Insection Size: " << cmdparams.inssize << std::endl;
    return 0;
}

int main(int argc, char* argv[]) {
    auto t_all_start = std::chrono::steady_clock::now();
    if(PerfromCMD(argc,argv))
        return 1;
    // 单独统计数据生成时间
    auto t_data_gen_start = std::chrono::steady_clock::now();
    std::vector<PSI::Item> ServerSet;
    std::vector<PSI::Label> LabelSet;
    // 打开输出文件
    std::ofstream output_file("/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/server_generated_data.txt");
    if (!output_file.is_open()) {
        std::cout << "Warning: Cannot open output file for writing" << std::endl;
    }
    
    // 存储所有数据用于按列输出
    std::vector<std::array<uint8_t, 16>> random_ids_16;
    std::vector<std::vector<uint8_t>> share_bytes;
    std::vector<std::array<uint8_t, PSI::Label_byte_size>> labels;
    
    for(size_t idx = 0; idx < cmdparams.setsize; idx++){
        // 使用动态的Item_byte_size
        std::array<uint8_t, PSI::Item_byte_size> item_data;
        RAND_bytes(item_data.data(), PSI::Item_byte_size);
        ServerSet.emplace_back(item_data);
        
        // 分离16字节随机ID和byte_count字节share
        std::array<uint8_t, 16> random_id_16;
        std::memcpy(random_id_16.data(), item_data.data(), 16);
        random_ids_16.push_back(random_id_16);
        
        if(PSI::Item_byte_size > 16){
            size_t byte_count = PSI::Item_byte_size - 16;
            std::vector<uint8_t> share_data(byte_count);
            std::memcpy(share_data.data(), item_data.data() + 16, byte_count);
            share_bytes.push_back(share_data);
        } else {
            share_bytes.push_back(std::vector<uint8_t>());
        }
        
        if(PSI::Label_byte_size > 0){
            std::array<uint8_t, PSI::Label_byte_size> label_data;
            RAND_bytes(label_data.data(), PSI::Label_byte_size);
            LabelSet.emplace_back(gsl::make_span(label_data));
            labels.push_back(label_data);
        }
    }
    // 读取sendershare字节数据
    auto sendershare_bytes = readSendershareBytes();
    
    
    // 处理交集替换
    for(size_t idx = 0; idx <cmdparams.inssize; idx++){
        if(idx < ServerSet.size()){
            // 将insection数据转换为Item_byte_size格式
            std::array<uint8_t, PSI::Item_byte_size> item_data;
            // 将insection的16字节数据复制到item_data的前16字节
            std::memcpy(item_data.data(), &insection[idx], 16);
            
            // 如果Item_byte_size > 16，用sendershare数据填充剩余字节
            if(PSI::Item_byte_size > 16){
                size_t remaining_bytes = PSI::Item_byte_size - 16;
                
                if(idx < sendershare_bytes.size() && sendershare_bytes[idx].size() >= remaining_bytes){
                    // 使用sendershare数据填充剩余字节
                    std::memcpy(item_data.data() + 16, sendershare_bytes[idx].data(), remaining_bytes);
                    std::cout << "Replaced bytes for intersection item " << idx << " with sendershare data" << std::endl;
                } else {
                    // 如果sendershare数据不足，用随机数据填充
                    RAND_bytes(item_data.data() + 16, remaining_bytes);
                    std::cout << "Warning: Not enough sendershare data for item " << idx << ", using random data" << std::endl;
                }
            }
            ServerSet[idx] = PSI::Item(item_data);
            
            // 更新存储的数据（交集替换后的数据）
            std::memcpy(random_ids_16[idx].data(), item_data.data(), 16);
            if(PSI::Item_byte_size > 16){
                size_t byte_count = PSI::Item_byte_size - 16;
                share_bytes[idx].resize(byte_count);
                std::memcpy(share_bytes[idx].data(), item_data.data() + 16, byte_count);
            }
        }
    }
    
    
    // 按列输出两列数据到文件
    if (output_file.is_open()) {
        // 输出列标题
        output_file << "16字节随机ID(替换交集后)+share Label" << std::endl;
        
        // 按行输出数据
        for(size_t idx = 0; idx < cmdparams.setsize; idx++){
            // 第一列：16字节随机ID（替换交集后的）+ share
            for (size_t i = 0; i < 16; i++) {
                output_file << std::hex << std::setfill('0') << std::setw(2) << static_cast<int>(random_ids_16[idx][i]);
            }
            // 添加share数据
            if(!share_bytes[idx].empty()){
                for (size_t i = 0; i < share_bytes[idx].size(); i++) {
                    output_file << std::hex << std::setfill('0') << std::setw(2) << static_cast<int>(share_bytes[idx][i]);
                }
            }
            output_file << " ";
            
            // 第二列：Label
            if(PSI::Label_byte_size > 0 && idx < labels.size()){
                for (size_t i = 0; i < PSI::Label_byte_size; i++) {
                    output_file << std::hex << std::setfill('0') << std::setw(2) << static_cast<int>(labels[idx][i]);
                }
            }
            output_file << std::dec << std::endl;
        }
        
        output_file.close();
        std::cout << "Server generated data saved to: server_generated_data.txt" << std::endl;
    }
    auto t_data_gen_end = std::chrono::steady_clock::now();
    std::cout << "Prepare TestData Finish" << std::endl;
    PSI::StopWatch serverclocks("server");
    PSI::ThreadPoolMgr::SetThreadCount(cmdparams.threads);
    serverclocks.setpoint("start");
    droidCrypto::CSocketChannel chans("127.0.0.1", 8000, true);
    serverclocks.setpoint("Network start");
    auto t_online_start = std::chrono::steady_clock::now();
    PSI::Server::PSIServer server(cmdparams.setsize,chans);
    serverclocks.setpoint("start");
    server.DHBased_SIMDDPF_PSI_start("127.0.0.1:51000","127.0.0.1:51002",ServerSet,LabelSet);
    auto t_online_end = std::chrono::steady_clock::now();
    serverclocks.setpoint("ALL Finish");
    std::cout << "------------------- ALL Server Finish ---------------------" << std::endl;
    serverclocks.printTimePointRecord();
    auto t_all_end = std::chrono::steady_clock::now();
    double data_gen = std::chrono::duration<double, std::milli>(t_data_gen_end - t_data_gen_start).count();
    double online = std::chrono::duration<double, std::milli>(t_online_end - t_online_start).count();
    double offline = std::chrono::duration<double, std::milli>(t_online_start - t_data_gen_end).count();
    std::ofstream fout("/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/cli/time.txt", std::ios::app);
    fout << "Server data_gen: " << data_gen << " ms" << std::endl;
    fout << "Server online: " << online << " ms, offline: " << offline << " ms" << std::endl;
    // 写出本角色的在线/离线时间供汇总
    {
        std::ofstream role_file("/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/role_times_server.txt", std::ios::trunc);
        if (role_file.is_open()) {
            role_file << online << "\n" << offline << "\n";
        }
    }
    return 0;
}

