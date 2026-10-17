/* 自写授权样本 crackme：读输入 -> 异或校验 -> 打印 OK/NO。仅用于MCP逆向链路自测，无第三方代码 */
#include <stdio.h>
#include <string.h>
static const char SECRET[] = "REA-MCP-LAB-2026";
static int check_key(const char *s){
    unsigned char k = 0x5A;
    for (size_t i=0;i<strlen(SECRET);i++){
        if (((unsigned char)s[i] ^ k) != (unsigned char)SECRET[i]) return 0;
        k += 0x11;
    }
    return s[strlen(SECRET)]=='\0';
}
int main(int argc,char**argv){
    if(argc<2){ printf("usage: %s <key>\n", argv[0]); return 2; }
    if(check_key(argv[1])){ printf("Correct!\n"); return 0; }
    printf("Wrong key\n"); return 1;
}
