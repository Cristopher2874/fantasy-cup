type FileDropzoneProps = {
  isDragging: boolean;
  onDrop: (files: FileList) => void;
  onFileInput: (files: FileList) => void;
  onSetDragging: (value: boolean) => void;
};

export function FileDropzone({ isDragging, onDrop, onFileInput, onSetDragging }: FileDropzoneProps) {
  return (
    <div
      className={isDragging ? 'dropzone dropzone-active' : 'dropzone'}
      onDragOver={(event) => {
        event.preventDefault();
        onSetDragging(true);
      }}
      onDragLeave={() => onSetDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        onSetDragging(false);
        onDrop(event.dataTransfer.files);
      }}
    >
      <input
        id="skillFiles"
        type="file"
        accept=".zip,application/zip,application/x-zip-compressed"
        multiple
        onChange={(event) => {
          if (event.target.files) {
            onFileInput(event.target.files);
          }
        }}
      />
      <label htmlFor="skillFiles">
        <strong>Drop skill ZIPs here</strong>
        <span>or browse for up to five files</span>
      </label>
    </div>
  );
}
