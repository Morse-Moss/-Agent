import { Button, Empty, Input, Space, Typography } from "antd";
import { useRef, useEffect } from "react";

import type { ChatMessage } from "../../lib/types";

interface ChatPanelProps {
  messages: ChatMessage[];
  inputValue: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  sending?: boolean;
  placeholder?: string;
}

export function ChatPanel({
  messages,
  inputValue,
  onInputChange,
  onSend,
  sending,
  placeholder = "输入消息...",
}: ChatPanelProps): JSX.Element {
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages.length]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div
        ref={listRef}
        style={{ flex: 1, overflowY: "auto", padding: "12px 0", minHeight: 200 }}
      >
        {messages.length === 0 ? (
          <Empty description="开始对话" />
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                marginBottom: 12,
                textAlign: msg.sender_type === "user" ? "right" : "left",
              }}
            >
              <Typography.Text
                type={msg.sender_type === "user" ? undefined : "secondary"}
                style={{
                  display: "inline-block",
                  padding: "8px 12px",
                  borderRadius: 12,
                  background: msg.sender_type === "user" ? "#0f3d3e" : "#f5f5f5",
                  color: msg.sender_type === "user" ? "#fff" : undefined,
                  maxWidth: "80%",
                  whiteSpace: "pre-wrap",
                  textAlign: "left",
                }}
              >
                {msg.content}
              </Typography.Text>
            </div>
          ))
        )}
      </div>
      <Space.Compact style={{ width: "100%" }}>
        <Input.TextArea
          value={inputValue}
          onChange={(e) => onInputChange(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          placeholder={placeholder}
          autoSize={{ minRows: 2, maxRows: 4 }}
          disabled={sending}
        />
        <Button type="primary" onClick={onSend} loading={sending} style={{ height: "auto" }}>
          发送
        </Button>
      </Space.Compact>
    </div>
  );
}
