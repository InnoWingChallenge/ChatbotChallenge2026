# 環境配置方法
0.（建議）使用venv（aka python虛擬環境），所有人用python3.12（3.11，3.10也可以，但我怕不同版本的package可能有細微分別，未免麻煩還是都用同一個python吧）！如果沒有就先安裝python3.12！
指令：
```bash
   cd submission_repo
   python3.12 -m venv .venv
   # macOS & Linux:
   source .venv/bin/activate
   # Windows:
   .venv\Scripts\activate

   pip install -r requirements.txt
   ```

1. 所有code會寫在submission_repo裏，所以記得cd submission——repo先把folder切換過去！
```bash
   #如果用venv就先啟動虛擬環境
   source .venv/bin/activate
```
檢查你沒有裝錯版本：
```bash
    python -V
    # 正常應該返回 Python 3.12.xx 如果不是3.12就是裝錯了！
```
安裝需要的軟件包
```bash
   pip install -r requirements.txt
```
2. 將你的api放在名為 .env 的環境，然後用check_setup.py檢查
```bash
   cp .env.example .env   # then fill in your key
   python check_setup.py  # verify your setup before Workshop 1
   ```
（2.5）如果你不是用vscode，記得把editor生成的文件放到.gitignore裏面，以免它們被上傳到github（/.vscode 我幫大家加了，所以用vscode應該就沒這個問題）如果你在project裡放了點personal的東西（例如用戶名和密碼）也請提前把相關文件寫在.gitignore裏面！！！

3. 大功告成！